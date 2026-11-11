"""Unit tests for SelfHealingReflector."""

from agent.llm_provider import OfflineSimulationProvider
from agent.models import ExecutionResult, TestOutcome
from agent.reflector import SelfHealingReflector


def test_reflection_on_failure():
    llm = OfflineSimulationProvider()
    reflector = SelfHealingReflector(llm)

    exec_res = ExecutionResult(
        success=False,
        exit_code=1,
        stdout="FAIL test_solution.py::test_eviction_order",
        stderr="AssertionError: assert None == 1",
        tests=[
            TestOutcome(name="test_eviction_order", status="FAILED", error_message="AssertionError: assert None == 1")
        ],
    )

    reflection = reflector.reflect(
        objective="LRU Cache with eviction bug",
        code="class LRUCache: pass",
        test_code="def test_eviction_order(): pass",
        execution_result=exec_res,
        iteration=1,
    )

    assert reflection.iteration == 1
    assert reflection.root_cause != ""
    assert len(reflection.flawed_assumptions) > 0
    assert reflection.corrective_action != ""
