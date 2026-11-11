"""Unit tests for AgentOrchestrator state machine and HITL review gate."""

from agent.llm_provider import OfflineSimulationProvider
from agent.models import TaskStatus
from agent.orchestrator import AgentOrchestrator


def test_orchestrator_initialization():
    llm = OfflineSimulationProvider()
    orch = AgentOrchestrator(llm_provider=llm)

    state = orch.create_task("Implement Fibonacci sequence", require_hitl=True)
    assert state.status == TaskStatus.PENDING
    assert state.task_id in orch.tasks
    assert len(state.thought_log) == 1


def test_orchestrator_stepping_to_hitl_gate():
    llm = OfflineSimulationProvider()
    orch = AgentOrchestrator(llm_provider=llm)

    state = orch.create_task("LRU cache", require_hitl=True)

    # Step 1: PENDING -> PLANNING
    orch.step(state.task_id)
    assert state.status == TaskStatus.CODING
    assert state.plan is not None

    # Step 2: CODING -> SECURITY_CHECK
    orch.step(state.task_id)
    assert state.status == TaskStatus.SECURITY_CHECK
    assert state.current_code != ""

    # Step 3: SECURITY_CHECK -> HITL_REVIEW (since require_hitl is True)
    orch.step(state.task_id)
    assert state.status == TaskStatus.HITL_REVIEW
    assert state.security_report.passed is True


def test_hitl_approval_and_execution():
    llm = OfflineSimulationProvider()
    orch = AgentOrchestrator(llm_provider=llm)

    state = orch.create_task("LRU cache", require_hitl=True, max_iterations=3)

    # Run until HITL gate
    orch.run_until_stop(state.task_id)
    assert state.status == TaskStatus.HITL_REVIEW

    # Approve decision
    orch.process_hitl_decision(state.task_id, action="APPROVE", reviewer="Dr. Turing")
    assert state.status == TaskStatus.EXECUTING
    assert len(state.hitl_history) == 1
    assert state.hitl_history[0].reviewer == "Dr. Turing"


def test_autonomous_self_healing_without_hitl():
    llm = OfflineSimulationProvider()
    orch = AgentOrchestrator(llm_provider=llm)

    # Disable HITL to test full autonomous loop convergence
    state = orch.create_task("LRU cache", require_hitl=False, max_iterations=4)
    orch.run_until_stop(state.task_id)

    # Verify that agent reached completed or executed healing iterations
    assert state.status in (TaskStatus.COMPLETED, TaskStatus.REFLECTING, TaskStatus.CODING)
    assert state.current_iteration >= 1
    assert len(state.reflections) >= 1
