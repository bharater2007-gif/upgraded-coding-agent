"""Unit tests for resilient LLM fallback mechanism (503, 429, timeouts)."""

from typing import Optional

from agent.llm_provider import (
    BaseLLMProvider,
    FallbackLLMProvider,
    OfflineSimulationProvider,
)


class MockFlakyLLMProvider(BaseLLMProvider):
    """Simulates a live LLM experiencing transient 503 or 429 API errors."""

    def __init__(self, failure_mode: str = "503"):
        self.failure_mode = failure_mode
        self.should_succeed = False

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        if self.should_succeed:
            return '{"code": "# recovered", "test_code": "# test", "explanation": "recovered"}'

        if self.failure_mode == "503":
            raise RuntimeError("Gemini API returned status 503: The model is overloaded. Please try again later.")
        elif self.failure_mode == "429":
            raise RuntimeError("Gemini API returned status 429: Resource exhausted / rate limit exceeded.")
        elif self.failure_mode == "timeout":
            raise TimeoutError("Connection to generativelanguage.googleapis.com timed out.")
        else:
            raise ConnectionError("Failed to resolve host api.openai.com.")


def test_fallback_on_503_high_demand():
    flaky_primary = MockFlakyLLMProvider(failure_mode="503")
    sim_fallback = OfflineSimulationProvider()
    resilient_provider = FallbackLLMProvider(primary=flaky_primary, fallback=sim_fallback)

    assert resilient_provider.fallback_active is False

    # Trigger generation while primary returns 503
    response = resilient_provider.generate("Decompose the following high-level objective: LRU Cache")
    assert response is not None
    assert "subtasks" in response

    # Verify fallback state
    assert resilient_provider.fallback_active is True
    assert "503" in resilient_provider.fallback_message or "busy" in resilient_provider.fallback_message.lower()
    assert resilient_provider.fallback_count == 1


def test_fallback_on_429_rate_limit():
    flaky_primary = MockFlakyLLMProvider(failure_mode="429")
    sim_fallback = OfflineSimulationProvider()
    resilient_provider = FallbackLLMProvider(primary=flaky_primary, fallback=sim_fallback)

    response = resilient_provider.generate("Decompose the following high-level objective: Rate Limiter")
    assert response is not None
    assert resilient_provider.fallback_active is True
    assert "429" in resilient_provider.fallback_message or "rate-limited" in resilient_provider.fallback_message.lower()


def test_fallback_on_timeout():
    flaky_primary = MockFlakyLLMProvider(failure_mode="timeout")
    sim_fallback = OfflineSimulationProvider()
    resilient_provider = FallbackLLMProvider(primary=flaky_primary, fallback=sim_fallback)

    response = resilient_provider.generate("LRU cache")
    assert response is not None
    assert resilient_provider.fallback_active is True
    assert "timeout" in resilient_provider.fallback_message.lower() or "connection" in resilient_provider.fallback_message.lower()


def test_fallback_chat_failover():
    flaky_primary = MockFlakyLLMProvider(failure_mode="503")
    sim_fallback = OfflineSimulationProvider()
    resilient_provider = FallbackLLMProvider(primary=flaky_primary, fallback=sim_fallback)

    chat_res = resilient_provider.chat("Explain this bug", context={"objective": "LRU cache"})
    assert chat_res is not None
    assert "reply" in chat_res
    assert chat_res["fallback_active"] is True
    assert "busy" in chat_res["fallback_message"].lower() or "503" in chat_res["fallback_message"]


def test_fallback_resets_upon_primary_recovery():
    flaky_primary = MockFlakyLLMProvider(failure_mode="503")
    sim_fallback = OfflineSimulationProvider()
    resilient_provider = FallbackLLMProvider(primary=flaky_primary, fallback=sim_fallback)

    # 1. Fails -> fallback active
    resilient_provider.generate("LRU cache")
    assert resilient_provider.fallback_active is True

    # 2. Primary recovers
    flaky_primary.should_succeed = True
    res = resilient_provider.generate("LRU cache")
    assert "recovered" in res
    assert resilient_provider.fallback_active is False
    assert resilient_provider.fallback_message == ""
