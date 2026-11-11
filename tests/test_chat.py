"""Unit tests for the Interactive Copilot Chat feature."""

from agent.llm_provider import OfflineSimulationProvider
from agent.orchestrator import AgentOrchestrator


def test_copilot_chat_explain_bug():
    llm = OfflineSimulationProvider()
    orch = AgentOrchestrator(llm_provider=llm)

    task = orch.create_task("LRU Cache with eviction bug")
    # Step into coding to generate buggy code
    orch.step(task.task_id)
    orch.step(task.task_id)

    chat_res = orch.chat("Explain this bug", task_id=task.task_id)
    assert "reply" in chat_res
    assert "reasoning" in chat_res
    assert "LRU Cache" in chat_res["reply"] or "get()" in chat_res["reply"]
    assert "reasoning" in chat_res and len(chat_res["reasoning"]) > 0


def test_copilot_chat_self_healing_explanation():
    llm = OfflineSimulationProvider()
    orch = AgentOrchestrator(llm_provider=llm)

    chat_res = orch.chat("How does the self-healing loop work?")
    assert "ReAct" in chat_res["reply"] or "Reflexion" in chat_res["reply"] or "sandbox" in chat_res["reply"].lower()
    assert "reasoning" in chat_res


def test_copilot_chat_refactor_suggestions():
    llm = OfflineSimulationProvider()
    orch = AgentOrchestrator(llm_provider=llm)

    chat_res = orch.chat("Refactor this function to be faster")
    assert "Optimization" in chat_res["reply"] or "O(1)" in chat_res["reply"] or "refactor" in chat_res["reply"].lower()
    assert len(chat_res["reasoning"]) > 0


def test_copilot_chat_ast_security():
    llm = OfflineSimulationProvider()
    orch = AgentOrchestrator(llm_provider=llm)

    chat_res = orch.chat("Explain the AST security check")
    assert "SEC-001" in chat_res["reply"] or "subprocess" in chat_res["reply"] or "Security" in chat_res["reply"]
