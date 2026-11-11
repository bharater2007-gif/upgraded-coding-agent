"""Agent State Machine and HITL Orchestration Engine.

Drives the autonomous cycle:
PLAN -> CODE -> AST SECURITY AUDIT -> HITL REVIEW GATE -> EXECUTE & TEST -> REFLECT / HEAL -> COMPLETE
Provides fine-grained step execution, real-time thought logging, and interactive human oversight.
"""

from __future__ import annotations

import logging
import uuid
from typing import Dict, Optional

from agent.coder import CodeSynthesizer
from agent.llm_provider import BaseLLMProvider, get_llm_provider
from agent.models import (
    AgentState,
    CodePatch,
    HITLDecision,
    SecurityReport,
    TaskStatus,
)
from agent.planner import TaskPlanner
from agent.reflector import SelfHealingReflector
from sandbox.ast_security import scan_code_security
from sandbox.executor import SandboxExecutor

logger = logging.getLogger("Agent.Orchestrator")


class AgentOrchestrator:
    """Coordinates agent thought loop, execution sandbox, reflection, and HITL gate."""

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        sandbox_executor: Optional[SandboxExecutor] = None,
    ):
        self.llm = llm_provider or get_llm_provider()
        self.sandbox = sandbox_executor or SandboxExecutor()
        self.planner = TaskPlanner(self.llm)
        self.coder = CodeSynthesizer(self.llm)
        self.reflector = SelfHealingReflector(self.llm)
        self.tasks: Dict[str, AgentState] = {}

    def create_task(
        self,
        objective: str,
        require_hitl: bool = True,
        max_iterations: int = 4,
        target_file: str = "solution.py",
        test_file: str = "test_solution.py",
    ) -> AgentState:
        """Initialize a new autonomous coding task."""
        task_id = str(uuid.uuid4())[:8]
        state = AgentState(
            task_id=task_id,
            objective=objective,
            status=TaskStatus.PENDING,
            require_hitl=require_hitl,
            max_iterations=max_iterations,
            target_file=target_file,
            test_file=test_file,
        )
        state.add_thought(
            phase="INITIALIZATION",
            thought=f"Initialized coding objective: '{objective}'. HITL Review Gate is {'ENABLED' if require_hitl else 'DISABLED'}.",
        )
        self.tasks[task_id] = state
        return state

    def get_task(self, task_id: str) -> Optional[AgentState]:
        """Retrieve state for a given task ID."""
        return self.tasks.get(task_id)

    def step(self, task_id: str) -> AgentState:
        """Advance the agent by exactly one discrete state transition."""
        state = self.tasks.get(task_id)
        if not state:
            raise KeyError(f"Task {task_id} not found.")

        current = state.status

        # 1. PENDING -> PLANNING
        if current == TaskStatus.PENDING:
            state.status = TaskStatus.PLANNING
            state.add_thought(
                phase="PLANNING",
                thought="Decomposing high-level objective into structured subtasks with verification criteria.",
            )
            plan = self.planner.decompose(state.objective)
            state.plan = plan
            state.add_thought(
                phase="PLANNING",
                thought=f"Decomposed objective into {len(plan.subtasks)} verifiable subtasks.",
                detail=plan.rationale,
            )
            # Advance to CODING
            state.status = TaskStatus.CODING
            return state

        # 2. CODING -> SECURITY_CHECK
        elif current == TaskStatus.CODING:
            state.add_thought(
                phase="CODING",
                thought=f"Synthesizing implementation for iteration #{state.current_iteration}.",
            )
            if state.current_iteration == 0:
                code, test_code, patch = self.coder.synthesize_initial(
                    objective=state.objective,
                    plan=state.plan,
                    target_file=state.target_file,
                    test_file=state.test_file,
                )
            else:
                # Reflection-guided fix
                last_reflection = state.reflections[-1] if state.reflections else None
                code, test_code, patch = self.coder.synthesize_fix(
                    objective=state.objective,
                    current_code=state.current_code,
                    test_code=state.test_code,
                    reflection=last_reflection,
                    target_file=state.target_file,
                    test_file=state.test_file,
                )

            state.current_code = code
            state.test_code = test_code
            state.current_patch = patch

            state.add_thought(
                phase="CODING",
                thought="Code and test suite synthesized. Generated unified code patch.",
                detail=patch.explanation,
            )
            state.status = TaskStatus.SECURITY_CHECK
            return state

        # 3. SECURITY_CHECK -> HITL_REVIEW or EXECUTING
        elif current == TaskStatus.SECURITY_CHECK:
            state.add_thought(
                phase="SECURITY_CHECK",
                thought="Performing AST static security analysis to detect prohibited syscalls and imports.",
            )
            sec_report: SecurityReport = scan_code_security(state.current_code)
            state.security_report = sec_report

            if not sec_report.passed:
                state.add_thought(
                    phase="SECURITY_CHECK",
                    thought="CRITICAL AST SECURITY VIOLATIONS DETECTED. Execution blocked.",
                    detail="; ".join(v.message for v in sec_report.violations),
                )
                # If iterations remain, reflect and fix security violation
                if state.current_iteration < state.max_iterations:
                    state.status = TaskStatus.REFLECTING
                else:
                    state.status = TaskStatus.FAILED
                return state

            state.add_thought(
                phase="SECURITY_CHECK",
                thought=f"AST Security Audit passed successfully ({sec_report.scanned_nodes} nodes inspected, {sec_report.duration_ms:.2f}ms).",
            )

            # Check if HITL review is required before execution
            if state.require_hitl:
                state.status = TaskStatus.HITL_REVIEW
                state.add_thought(
                    phase="HITL_REVIEW",
                    thought="Awaiting human operator approval or code modification at HITL Review Gate.",
                )
            else:
                state.status = TaskStatus.EXECUTING

            return state

        # 4. HITL_REVIEW -> Waiting for human decision
        elif current == TaskStatus.HITL_REVIEW:
            # Cannot auto-step past HITL without approval
            state.add_thought(
                phase="HITL_REVIEW",
                thought="Still waiting at HITL Review Gate for human approval or feedback.",
            )
            return state

        # 5. EXECUTING -> REFLECTING or COMPLETED
        elif current == TaskStatus.EXECUTING:
            state.add_thought(
                phase="EXECUTING",
                thought="Executing code and test suite in isolated subprocess sandbox with Flake8 and pytest.",
            )
            exec_res = self.sandbox.execute_and_test(
                code=state.current_code,
                test_code=state.test_code,
                target_file=state.target_file,
                test_file=state.test_file,
                task_id=state.task_id,
            )
            state.execution_result = exec_res

            if exec_res.success:
                state.status = TaskStatus.COMPLETED
                state.add_thought(
                    phase="COMPLETED",
                    thought="All unit tests passed and code execution succeeded!",
                    detail=exec_res.summary,
                )
            else:
                state.add_thought(
                    phase="EXECUTING",
                    thought=f"Execution encountered failures: {exec_res.summary}",
                    detail=exec_res.stderr or exec_res.stdout,
                )
                if state.current_iteration < state.max_iterations:
                    state.status = TaskStatus.REFLECTING
                else:
                    state.status = TaskStatus.FAILED
                    state.add_thought(
                        phase="FAILED",
                        thought=f"Exceeded maximum self-healing iterations ({state.max_iterations}). Task marked failed.",
                    )

            return state

        # 6. REFLECTING -> CODING
        elif current == TaskStatus.REFLECTING:
            state.current_iteration += 1
            state.add_thought(
                phase="REFLECTING",
                thought=f"Commencing Self-Healing Reflection loop for iteration #{state.current_iteration}.",
            )
            reflection = self.reflector.reflect(
                objective=state.objective,
                code=state.current_code,
                test_code=state.test_code,
                execution_result=state.execution_result,
                iteration=state.current_iteration,
            )
            state.reflections.append(reflection)
            state.add_thought(
                phase="REFLECTING",
                thought=f"Formulated root-cause diagnosis: {reflection.root_cause}",
                detail=f"Action: {reflection.corrective_action}",
            )
            # Cycle back to CODING with reflection insights
            state.status = TaskStatus.CODING
            return state

        # Completed or Failed
        return state

    def run_until_stop(self, task_id: str, max_steps: int = 25) -> AgentState:
        """Run the agent autonomously until it completes, fails, or pauses at HITL Review Gate."""
        steps = 0
        state = self.tasks.get(task_id)
        if not state:
            raise KeyError(f"Task {task_id} not found.")

        while steps < max_steps:
            if state.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.REJECTED, TaskStatus.HITL_REVIEW):
                break
            self.step(task_id)
            steps += 1

        return state

    def process_hitl_decision(
        self,
        task_id: str,
        action: str,  # "APPROVE", "MODIFY", "REJECT", "REPLAN"
        feedback: Optional[str] = None,
        modified_code: Optional[str] = None,
        reviewer: str = "human_operator",
    ) -> AgentState:
        """Process human operator decision at HITL Review Gate."""
        state = self.tasks.get(task_id)
        if not state:
            raise KeyError(f"Task {task_id} not found.")

        decision = HITLDecision(
            action=action.upper(),
            reviewer=reviewer,
            feedback=feedback,
            modified_code=modified_code,
        )
        state.hitl_history.append(decision)

        act = action.upper()
        if act == "APPROVE":
            state.add_thought(
                phase="HITL_REVIEW",
                thought=f"Operator '{reviewer}' APPROVED the code patch.",
                detail=feedback or "Approved without additional comments.",
            )
            state.status = TaskStatus.EXECUTING

        elif act == "MODIFY":
            if modified_code:
                # Update current code with operator's manual edits
                old_code = state.current_code
                state.current_code = modified_code
                state.current_patch = CodePatch(
                    file_path=state.target_file,
                    original_code=old_code,
                    patched_code=modified_code,
                    explanation=f"Manual operator adjustment: {feedback or 'Code edited in review'}",
                )
            state.add_thought(
                phase="HITL_REVIEW",
                thought=f"Operator '{reviewer}' MODIFIED the code and approved for sandbox execution.",
                detail=feedback,
            )
            state.status = TaskStatus.EXECUTING

        elif act == "REJECT":
            state.add_thought(
                phase="HITL_REVIEW",
                thought=f"Operator '{reviewer}' REJECTED the code patch.",
                detail=feedback or "Rejected without feedback.",
            )
            if state.current_iteration < state.max_iterations:
                # Treat human feedback as a reflection signal to self-heal
                state.status = TaskStatus.REFLECTING
            else:
                state.status = TaskStatus.REJECTED

        elif act == "REPLAN":
            state.add_thought(
                phase="HITL_REVIEW",
                thought=f"Operator '{reviewer}' requested ARCHITECTURAL RE-PLANNING.",
                detail=feedback,
            )
            state.status = TaskStatus.PLANNING

        return state

    @property
    def fallback_status(self) -> Dict[str, Any]:
        """Return current LLM fallback status."""
        if hasattr(self.llm, "fallback_active"):
            return {
                "active": self.llm.fallback_active,
                "message": getattr(self.llm, "fallback_message", ""),
                "count": getattr(self.llm, "fallback_count", 0),
            }
        return {"active": False, "message": "", "count": 0}

    def chat(self, message: str, task_id: Optional[str] = None) -> Dict[str, Any]:
        """Conversational copilot interaction using current task context."""
        context = {}
        if task_id and task_id in self.tasks:
            state = self.tasks[task_id]
            last_err = ""
            if state.execution_result:
                last_err = (
                    state.execution_result.stderr
                    or state.execution_result.stdout
                    or state.execution_result.summary
                )
            last_ref = ""
            if state.reflections:
                last_ref = (
                    f"{state.reflections[-1].root_cause} -> "
                    f"{state.reflections[-1].corrective_action}"
                )

            context = {
                "objective": state.objective,
                "status": state.status.value,
                "target_file": state.target_file,
                "current_code": state.current_code,
                "errors": last_err,
                "reflection": last_ref,
            }

        response = self.llm.chat(message, context=context)
        fb = self.fallback_status
        if fb["active"]:
            response["fallback_active"] = True
            response["fallback_message"] = fb["message"]
        return response
