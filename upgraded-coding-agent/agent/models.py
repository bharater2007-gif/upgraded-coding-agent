"""Core data models and schemas for the Upgraded Coding Agent.

Defines Pydantic/dataclass structures for Agent states, task decomposition,
AST security results, execution telemetry, reflections, and HITL decisions.
"""

from __future__ import annotations

import difflib
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    CODING = "CODING"
    SECURITY_CHECK = "SECURITY_CHECK"
    HITL_REVIEW = "HITL_REVIEW"
    EXECUTING = "EXECUTING"
    REFLECTING = "REFLECTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


@dataclass
class SubTask:
    id: str
    title: str
    description: str
    status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    test_criteria: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SubTask:
        return cls(**data)


@dataclass
class TaskPlan:
    objective: str
    subtasks: List[SubTask] = field(default_factory=list)
    rationale: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective": self.objective,
            "subtasks": [st.to_dict() for st in self.subtasks],
            "rationale": self.rationale,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskPlan:
        subtasks = [SubTask.from_dict(st) for st in data.get("subtasks", [])]
        return cls(
            objective=data.get("objective", ""),
            subtasks=subtasks,
            rationale=data.get("rationale", ""),
            created_at=data.get("created_at", time.time()),
        )


@dataclass
class CodePatch:
    file_path: str
    original_code: str
    patched_code: str
    diff_unified: str = ""
    explanation: str = ""

    def __post_init__(self):
        if not self.diff_unified and (self.original_code or self.patched_code):
            orig_lines = self.original_code.splitlines(keepends=True)
            patch_lines = self.patched_code.splitlines(keepends=True)
            diff = difflib.unified_diff(
                orig_lines,
                patch_lines,
                fromfile=f"a/{self.file_path}",
                tofile=f"b/{self.file_path}",
            )
            self.diff_unified = "".join(diff)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CodePatch:
        return cls(**data)


@dataclass
class SecurityViolation:
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    rule: str
    message: str
    line_no: Optional[int] = None
    node_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SecurityViolation:
        return cls(**data)


@dataclass
class SecurityReport:
    passed: bool
    violations: List[SecurityViolation] = field(default_factory=list)
    scanned_nodes: int = 0
    scanned_imports: int = 0
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "scanned_nodes": self.scanned_nodes,
            "scanned_imports": self.scanned_imports,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SecurityReport:
        violations = [SecurityViolation.from_dict(v) for v in data.get("violations", [])]
        return cls(
            passed=data.get("passed", True),
            violations=violations,
            scanned_nodes=data.get("scanned_nodes", 0),
            scanned_imports=data.get("scanned_imports", 0),
            duration_ms=data.get("duration_ms", 0.0),
        )


@dataclass
class LinterViolation:
    file: str
    line: int
    column: int
    code: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LinterViolation:
        return cls(**data)


@dataclass
class LinterReport:
    passed: bool
    violations: List[LinterViolation] = field(default_factory=list)
    raw_output: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "raw_output": self.raw_output,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LinterReport:
        violations = [LinterViolation.from_dict(v) for v in data.get("violations", [])]
        return cls(
            passed=data.get("passed", True),
            violations=violations,
            raw_output=data.get("raw_output", ""),
        )


@dataclass
class TestOutcome:
    __test__ = False
    name: str
    status: str  # "PASSED", "FAILED", "ERROR", "SKIPPED"
    duration: float = 0.0
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TestOutcome:
        return cls(**data)


@dataclass
class ExecutionResult:
    success: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration: float = 0.0
    linter_report: Optional[LinterReport] = None
    tests: List[TestOutcome] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration": self.duration,
            "linter_report": self.linter_report.to_dict() if self.linter_report else None,
            "tests": [t.to_dict() for t in self.tests],
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionResult:
        linter = LinterReport.from_dict(data["linter_report"]) if data.get("linter_report") else None
        tests = [TestOutcome.from_dict(t) for t in data.get("tests", [])]
        return cls(
            success=data.get("success", False),
            exit_code=data.get("exit_code", 1),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            duration=data.get("duration", 0.0),
            linter_report=linter,
            tests=tests,
            summary=data.get("summary", ""),
        )


@dataclass
class ReflectionRecord:
    iteration: int
    root_cause: str
    flawed_assumptions: List[str] = field(default_factory=list)
    corrective_action: str = ""
    code_changes_needed: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ReflectionRecord:
        return cls(**data)


@dataclass
class HITLDecision:
    action: str  # "APPROVE", "REJECT", "MODIFY", "REPLAN"
    reviewer: str = "human_operator"
    feedback: Optional[str] = None
    modified_code: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> HITLDecision:
        return cls(**data)


@dataclass
class ThoughtLogEntry:
    step: int
    phase: str
    thought: str
    detail: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ThoughtLogEntry:
        return cls(**data)


@dataclass
class AgentState:
    task_id: str
    objective: str
    status: TaskStatus = TaskStatus.PENDING
    current_iteration: int = 0
    max_iterations: int = 4
    require_hitl: bool = True
    target_file: str = "solution.py"
    test_file: str = "test_solution.py"
    current_code: str = ""
    test_code: str = ""
    plan: Optional[TaskPlan] = None
    current_patch: Optional[CodePatch] = None
    security_report: Optional[SecurityReport] = None
    execution_result: Optional[ExecutionResult] = None
    reflections: List[ReflectionRecord] = field(default_factory=list)
    hitl_history: List[HITLDecision] = field(default_factory=list)
    thought_log: List[ThoughtLogEntry] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add_thought(self, phase: str, thought: str, detail: Optional[str] = None):
        entry = ThoughtLogEntry(
            step=len(self.thought_log) + 1,
            phase=phase,
            thought=thought,
            detail=detail,
            timestamp=time.time(),
        )
        self.thought_log.append(entry)
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "status": self.status.value,
            "current_iteration": self.current_iteration,
            "max_iterations": self.max_iterations,
            "require_hitl": self.require_hitl,
            "target_file": self.target_file,
            "test_file": self.test_file,
            "current_code": self.current_code,
            "test_code": self.test_code,
            "plan": self.plan.to_dict() if self.plan else None,
            "current_patch": self.current_patch.to_dict() if self.current_patch else None,
            "security_report": self.security_report.to_dict() if self.security_report else None,
            "execution_result": self.execution_result.to_dict() if self.execution_result else None,
            "reflections": [r.to_dict() for r in self.reflections],
            "hitl_history": [h.to_dict() for h in self.hitl_history],
            "thought_log": [t.to_dict() for t in self.thought_log],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentState:
        plan = TaskPlan.from_dict(data["plan"]) if data.get("plan") else None
        patch = CodePatch.from_dict(data["current_patch"]) if data.get("current_patch") else None
        sec = SecurityReport.from_dict(data["security_report"]) if data.get("security_report") else None
        exe = ExecutionResult.from_dict(data["execution_result"]) if data.get("execution_result") else None
        reflections = [ReflectionRecord.from_dict(r) for r in data.get("reflections", [])]
        hitl = [HITLDecision.from_dict(h) for h in data.get("hitl_history", [])]
        thoughts = [ThoughtLogEntry.from_dict(t) for t in data.get("thought_log", [])]

        return cls(
            task_id=data["task_id"],
            objective=data.get("objective", ""),
            status=TaskStatus(data.get("status", TaskStatus.PENDING)),
            current_iteration=data.get("current_iteration", 0),
            max_iterations=data.get("max_iterations", 4),
            require_hitl=data.get("require_hitl", True),
            target_file=data.get("target_file", "solution.py"),
            test_file=data.get("test_file", "test_solution.py"),
            current_code=data.get("current_code", ""),
            test_code=data.get("test_code", ""),
            plan=plan,
            current_patch=patch,
            security_report=sec,
            execution_result=exe,
            reflections=reflections,
            hitl_history=hitl,
            thought_log=thoughts,
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )
