"""Unit tests for TaskPlanner."""

from agent.llm_provider import OfflineSimulationProvider
from agent.planner import TaskPlanner


def test_task_decomposition():
    llm = OfflineSimulationProvider()
    planner = TaskPlanner(llm)

    plan = planner.decompose("Build an LRU cache with eviction logic.")
    assert plan is not None
    assert len(plan.subtasks) >= 3
    assert plan.rationale != ""
    assert any("ST-" in st.id for st in plan.subtasks)
    assert all(len(st.test_criteria) > 0 for st in plan.subtasks)
