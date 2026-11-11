"""Unified LLM Provider abstraction supporting Gemini, OpenAI, and Offline Simulation.

Provides structured prompt execution, JSON schema extraction, conversational copilot chat,
and resilient automatic failover (503/429/timeout -> Offline Simulation Engine).
"""

from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("Agent.LLMProvider")


class BaseLLMProvider(ABC):
    """Abstract interface for LLM calls."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        """Generate text from the LLM."""
        pass

    def chat(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Conversational copilot interaction with internal reasoning."""
        context_str = ""
        if context:
            context_str = (
                f"\nCURRENT TASK CONTEXT:\n"
                f"- Objective: {context.get('objective', 'N/A')}\n"
                f"- Status: {context.get('status', 'N/A')}\n"
                f"- Target File: {context.get('target_file', 'solution.py')}\n"
                f"- Current Code:\n```python\n{context.get('current_code', 'No code yet')}\n```\n"
                f"- Latest Errors/Output:\n{context.get('errors', 'None')}\n"
                f"- Latest Reflection: {context.get('reflection', 'None')}\n"
            )

        system_prompt = (
            "You are an expert AI Coding Agent Copilot and Computer Science Mentor. "
            "Help the developer understand code, explain bugs, describe the self-healing loop, "
            "or refactor algorithms for optimal performance. Format output with clean Markdown "
            "and syntax-highlighted code blocks. Provide both a direct response and internal reasoning."
        )

        prompt = (
            f"{context_str}\n"
            f"User Question: {user_message}\n\n"
            f"Please respond with clear, well-structured GitHub-flavored Markdown."
        )

        reply = self.generate(prompt, system_instruction=system_prompt, temperature=0.3)
        return {
            "reply": reply,
            "reasoning": "Evaluated user question against current task context and synthesized structured guidance.",
            "fallback_active": False,
            "fallback_message": "",
        }


class GeminiProvider(BaseLLMProvider):
    """Direct HTTP client for Google Gemini API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-1.5-flash",
        timeout: float = 45.0,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.timeout = timeout
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")

        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        contents = [{"parts": [{"text": prompt}]}]
        body: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
            },
        }

        if system_instruction:
            body["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        headers = {"Content-Type": "application/json"}
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=headers, json=body)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Gemini API returned status {response.status_code}: {response.text}"
                )
            data = response.json()
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return text
            except (KeyError, IndexError) as err:
                raise RuntimeError(f"Unexpected Gemini response structure: {data}") from err


class OpenAIProvider(BaseLLMProvider):
    """Direct HTTP client for OpenAI Chat Completions API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
        timeout: float = 45.0,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.timeout = timeout

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set.")

        url = f"{self.base_url}/chat/completions"
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        body: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=headers, json=body)
            if response.status_code != 200:
                raise RuntimeError(
                    f"OpenAI API returned status {response.status_code}: {response.text}"
                )
            data = response.json()
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as err:
                raise RuntimeError(f"Unexpected OpenAI response: {data}") from err


class FallbackLLMProvider(BaseLLMProvider):
    """Resilient LLM Provider wrapping a primary provider with automatic failover to simulation."""

    def __init__(self, primary: BaseLLMProvider, fallback: BaseLLMProvider):
        self.primary = primary
        self.fallback = fallback
        self.fallback_active: bool = False
        self.fallback_message: str = ""
        self.fallback_count: int = 0

    @property
    def active_provider_name(self) -> str:
        if self.fallback_active:
            return f"{self.primary.__class__.__name__} -> {self.fallback.__class__.__name__} (Failover Active)"
        return self.primary.__class__.__name__

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        try:
            res = self.primary.generate(prompt, system_instruction, temperature, json_mode)
            self.fallback_active = False
            self.fallback_message = ""
            return res
        except Exception as exc:
            err_msg = str(exc)
            logger.warning(
                f"Primary LLM provider {self.primary.__class__.__name__} failed: {err_msg}. Triggering fallback."
            )
            self.fallback_active = True
            self.fallback_count += 1

            if "503" in err_msg or "high demand" in err_msg.lower() or "overloaded" in err_msg.lower() or "unavailable" in err_msg.lower():
                self.fallback_message = "Live API busy (503) — seamless failover to Simulation Engine active"
            elif "429" in err_msg or "rate limit" in err_msg.lower() or "quota" in err_msg.lower() or "resource_exhausted" in err_msg.lower():
                self.fallback_message = "Live API rate-limited (429) — seamless failover to Simulation Engine active"
            elif "connection" in err_msg.lower() or "timeout" in err_msg.lower() or "connect" in err_msg.lower():
                self.fallback_message = "Live API connection timeout — seamless failover to Simulation Engine active"
            else:
                self.fallback_message = f"Live API unavailable ({exc.__class__.__name__}) — seamless failover to Simulation Engine active"

            return self.fallback.generate(prompt, system_instruction, temperature, json_mode)

    def chat(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            res = self.primary.chat(user_message, context)
            self.fallback_active = False
            self.fallback_message = ""
            return res
        except Exception as exc:
            err_msg = str(exc)
            logger.warning(f"Primary LLM chat failed: {err_msg}. Delegating to fallback.")
            self.fallback_active = True
            self.fallback_count += 1

            if "503" in err_msg or "high demand" in err_msg.lower() or "unavailable" in err_msg.lower():
                self.fallback_message = "Live API busy (503) — seamless failover to Simulation Engine active"
            elif "429" in err_msg or "rate limit" in err_msg.lower() or "quota" in err_msg.lower():
                self.fallback_message = "Live API rate-limited (429) — seamless failover to Simulation Engine active"
            else:
                self.fallback_message = "Live API busy — seamless failover to Simulation Engine active"

            fallback_res = self.fallback.chat(user_message, context)
            fallback_res["fallback_active"] = True
            fallback_res["fallback_message"] = self.fallback_message
            return fallback_res


class OfflineSimulationProvider(BaseLLMProvider):
    """Deterministic simulation provider for zero-cost academic demonstration and testing.

    Accurately mirrors realistic multi-step planning, buggy initial implementation,
    root-cause reflection diagnostics, self-healed correct patches, and conversational copilot inquiries.
    """

    def __init__(self):
        self.call_history: List[Dict[str, Any]] = []

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        self.call_history.append({
            "prompt": prompt,
            "system_instruction": system_instruction,
            "json_mode": json_mode,
        })

        lower_prompt = prompt.lower()

        # 1. Planning phase
        if "decompose the following high-level objective" in lower_prompt or "planning" in lower_prompt:
            return json.dumps({
                "rationale": "Decompose into core algorithm, edge cases, and deterministic unit tests.",
                "subtasks": [
                    {
                        "id": "ST-1",
                        "title": "Define Type Signatures and Core Interface",
                        "description": "Create standard class or function signature with strict type hints.",
                        "test_criteria": ["Interface conforms to specification"],
                    },
                    {
                        "id": "ST-2",
                        "title": "Implement Core Algorithmic Logic",
                        "description": "Construct primary processing logic handling normal workflows.",
                        "test_criteria": ["Normal input test cases pass"],
                    },
                    {
                        "id": "ST-3",
                        "title": "Handle Edge Cases & Bounds",
                        "description": "Handle boundary conditions, empty collections, and zero values.",
                        "test_criteria": ["Boundary and negative tests pass"],
                    },
                    {
                        "id": "ST-4",
                        "title": "Verify Style, Cleanliness, and Security",
                        "description": "Ensure zero Flake8 violations and eliminate unsafe AST calls.",
                        "test_criteria": ["Flake8 returns 0 violations", "AST security audit passes"],
                    },
                ],
            })

        # 2. Reflection phase
        if "self-reflection analysis" in lower_prompt or "reflect on the execution failure" in lower_prompt:
            return json.dumps({
                "root_cause": "The previous implementation contained an off-by-one or missing boundary guard on empty/boundary inputs, causing pytest assertion failures.",
                "flawed_assumptions": [
                    "Assumed inputs would always be strictly positive",
                    "Overlooked zero or negative index handling in boundary checks",
                    "Unformatted trailing whitespace triggering Flake8 warning",
                ],
                "corrective_action": "Add explicit boundary check for zero/empty inputs, correct the loop bounds, and format according to PEP8.",
                "code_changes_needed": "Update boundary conditional and ensure clean returns.",
            })

        # 3. Coding phase
        is_fix = "previous attempt failed" in lower_prompt or "reflection" in lower_prompt or "iteration" in lower_prompt

        # Scenario: LRU Cache
        if "lru cache" in lower_prompt:
            if not is_fix:
                code = '''"""LRU Cache Implementation."""

from typing import Any, Dict, Optional


class LRUCache:
    """Least Recently Used (LRU) Cache with fixed capacity."""

    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        self.capacity = capacity
        self.cache: Dict[str, Any] = {}
        self.order: list[str] = []

    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None
        # BUG: Intentionally omitting updating self.order on get() for self-healing demonstration
        return self.cache[key]

    def put(self, key: str, value: Any) -> None:
        if key in self.cache:
            self.order.remove(key)
        elif len(self.cache) >= self.capacity:
            oldest = self.order.pop(0)
            del self.cache[oldest]
        self.cache[key] = value
        self.order.append(key)
'''
                test = '''"""Tests for LRU Cache."""

import pytest
from solution import LRUCache


def test_basic_put_get():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    assert cache.get("b") == 2


def test_eviction_order():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    # Access 'a', so 'b' becomes least recently used
    assert cache.get("a") == 1
    cache.put("c", 3)  # should evict 'b'
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3
'''
            else:
                code = '''"""LRU Cache Implementation - Self-Healed & Flake8 Compliant."""

from collections import OrderedDict
from typing import Any, Optional


class LRUCache:
    """Least Recently Used (LRU) Cache backed by OrderedDict."""

    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        self.capacity = capacity
        self.cache: OrderedDict[str, Any] = OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: str, value: Any) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        elif len(self.cache) >= self.capacity:
            self.cache.popitem(last=False)
        self.cache[key] = value
'''
                test = '''"""Tests for LRU Cache."""

import pytest
from solution import LRUCache


def test_basic_put_get():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    assert cache.get("b") == 2


def test_eviction_order():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    # Access 'a', so 'b' becomes least recently used
    assert cache.get("a") == 1
    cache.put("c", 3)  # should evict 'b'
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3


def test_invalid_capacity():
    with pytest.raises(ValueError):
        LRUCache(0)
'''
            return json.dumps({
                "code": code,
                "test_code": test,
                "explanation": "Self-healed LRU Cache utilizing OrderedDict for O(1) eviction and correct access ordering.",
            })

        # Scenario: Rate Limiter
        if "rate limiter" in lower_prompt:
            if not is_fix:
                code = '''"""Token Bucket Rate Limiter."""

import time


class RateLimiter:
    """Token bucket rate limiter with leak mechanism."""

    def __init__(self, max_tokens: int, refill_rate_per_sec: float):
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate_per_sec
        self.tokens = max_tokens
        self.last_refill = time.time()

    def allow_request(self, tokens: int = 1) -> bool:
        # BUG: Fails to refill tokens over time
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
'''
                test = '''"""Unit tests for RateLimiter."""

import time
from solution import RateLimiter


def test_burst_capacity():
    limiter = RateLimiter(max_tokens=3, refill_rate_per_sec=10.0)
    assert limiter.allow_request(1) is True
    assert limiter.allow_request(1) is True
    assert limiter.allow_request(1) is True
    assert limiter.allow_request(1) is False


def test_refill_mechanism():
    limiter = RateLimiter(max_tokens=2, refill_rate_per_sec=50.0)
    assert limiter.allow_request(2) is True
    assert limiter.allow_request(1) is False
    time.sleep(0.05)  # wait 50ms -> 2.5 tokens added
    assert limiter.allow_request(1) is True
'''
            else:
                code = '''"""Token Bucket Rate Limiter - Self-Healed & Flake8 Compliant."""

import time


class RateLimiter:
    """Thread-safe simulated token bucket rate limiter."""

    def __init__(self, max_tokens: int, refill_rate_per_sec: float):
        if max_tokens <= 0 or refill_rate_per_sec <= 0:
            raise ValueError("Parameters must be strictly positive")
        self.max_tokens = float(max_tokens)
        self.refill_rate = float(refill_rate_per_sec)
        self.tokens = float(max_tokens)
        self.last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def allow_request(self, tokens: int = 1) -> bool:
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
'''
                test = '''"""Unit tests for RateLimiter."""

import time
from solution import RateLimiter


def test_burst_capacity():
    limiter = RateLimiter(max_tokens=3, refill_rate_per_sec=10.0)
    assert limiter.allow_request(1) is True
    assert limiter.allow_request(1) is True
    assert limiter.allow_request(1) is True
    assert limiter.allow_request(1) is False


def test_refill_mechanism():
    limiter = RateLimiter(max_tokens=2, refill_rate_per_sec=50.0)
    assert limiter.allow_request(2) is True
    assert limiter.allow_request(1) is False
    time.sleep(0.05)  # wait 50ms -> 2.5 tokens added
    assert limiter.allow_request(1) is True
'''
            return json.dumps({
                "code": code,
                "test_code": test,
                "explanation": "Self-healed Rate Limiter calculating continuous time-delta refills.",
            })

        # Generic default scenario (Fibonacci or Math)
        if not is_fix:
            code = '''"""Fibonacci Sequence Generator."""


def fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number."""
    # BUG: Off-by-one error and missing negative input check
    if n == 0:
        return 1
    if n == 1:
        return 1
    return fibonacci(n - 1) + fibonacci(n - 2)
'''
            test = '''"""Tests for Fibonacci."""

import pytest
from solution import fibonacci


def test_fibonacci_base():
    assert fibonacci(0) == 0
    assert fibonacci(1) == 1
    assert fibonacci(2) == 1
    assert fibonacci(3) == 2
    assert fibonacci(4) == 3
    assert fibonacci(5) == 5


def test_fibonacci_negative():
    with pytest.raises(ValueError):
        fibonacci(-1)
'''
        else:
            code = '''"""Fibonacci Sequence Generator - Self-Healed & Memoized."""


def fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number with strict validation."""
    if n < 0:
        raise ValueError("Input must be a non-negative integer")
    if n == 0:
        return 0
    if n == 1:
        return 1

    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
'''
            test = '''"""Tests for Fibonacci."""

import pytest
from solution import fibonacci


def test_fibonacci_base():
    assert fibonacci(0) == 0
    assert fibonacci(1) == 1
    assert fibonacci(2) == 1
    assert fibonacci(3) == 2
    assert fibonacci(4) == 3
    assert fibonacci(5) == 5


def test_fibonacci_negative():
    with pytest.raises(ValueError):
        fibonacci(-1)
'''

        return json.dumps({
            "code": code,
            "test_code": test,
            "explanation": "Synthesized code with deterministic test verification.",
        })

    def chat(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Provide intelligent, structured conversational responses for Copilot queries."""
        lower_msg = user_message.lower().strip()
        ctx = context or {}
        objective = ctx.get("objective", "Autonomous Coding Task")
        errors = ctx.get("errors", "")
        current_code = ctx.get("current_code", "")

        # 1. Explain Bug
        if "explain" in lower_msg and "bug" in lower_msg:
            if "lru" in objective.lower():
                reply = (
                    "### 🔍 Bug Analysis: LRU Cache Eviction Ordering\n\n"
                    "The issue in the unhealed implementation is inside `get()`:\n\n"
                    "```python\ndef get(self, key: str) -> Optional[Any]:\n"
                    "    if key not in self.cache:\n"
                    "        return None\n"
                    "    # BUG: Forgets to update access recency!\n"
                    "    return self.cache[key]\n```\n\n"
                    "**Why this fails:**\n"
                    "- Under LRU semantics, retrieving an item via `get(key)` must update its status to **most recently used**.\n"
                    "- Without reordering, the accessed key remains at the front of eviction candidates. When `put()` exceeds capacity, the wrong key is deleted, triggering a failure in `test_eviction_order`.\n\n"
                    "**The Fix:**\n"
                    "Utilize `collections.OrderedDict` and invoke `self.cache.move_to_end(key)` upon every access."
                )
                reasoning = "Diagnosed omitted state modification in query operation using LRU invariant rules."
            elif "rate" in objective.lower():
                reply = (
                    "### 🔍 Bug Analysis: Token Bucket Refill Stagnation\n\n"
                    "The initial rate limiter implementation failed to replenish tokens over time:\n\n"
                    "```python\ndef allow_request(self, tokens: int = 1) -> bool:\n"
                    "    # BUG: Tokens are decremented but never refilled dynamically\n"
                    "    if self.tokens >= tokens:\n"
                    "        self.tokens -= tokens\n"
                    "        return True\n"
                    "    return False\n```\n\n"
                    "**Why this fails:**\n"
                    "- Once the initial burst bucket of tokens is depleted, all subsequent requests are rejected forever.\n"
                    "- The fix calculates `elapsed = now - last_refill` and continuously restores `tokens = min(max_tokens, tokens + elapsed * refill_rate)`."
                )
                reasoning = "Traced continuous time-delta replenishment omission against token bucket specification."
            elif "fibonacci" in objective.lower():
                reply = (
                    "### 🔍 Bug Analysis: Fibonacci Edge & Boundary Conditions\n\n"
                    "The unhealed code exhibited two classic defects:\n\n"
                    "1. **Missing Negative Input Guard:** Passing `n < 0` caused infinite recursion until stack overflow.\n"
                    "2. **Base Case Off-By-One:** Returned `1` for `n = 0`, violating $F_0 = 0$.\n\n"
                    "```python\ndef fibonacci(n: int) -> int:\n"
                    "    if n < 0:\n"
                    "        raise ValueError('Input must be a non-negative integer')\n"
                    "    if n == 0: return 0\n"
                    "    if n == 1: return 1\n"
                    "    # Iterative O(N) loop with O(1) space\n```"
                )
                reasoning = "Identified boundary condition violation ($F_0=0$) and omitted precondition assertion."
            else:
                reply = (
                    f"### 🔍 Failure Traceback & Bug Explanation\n\n"
                    f"**Objective:** {objective}\n\n"
                    f"**Detected Errors:**\n```text\n{errors or 'Assertion failure during test suite evaluation'}\n```\n\n"
                    f"The unit tests caught an unexpected output or exception. The self-healing loop captures this stderr, "
                    f"formulates root-cause hypotheses, and generates a targeted diff to satisfy all test criteria."
                )
                reasoning = "Analyzed test assertion tracebacks from sandbox execution logs."

        # 2. How does self-healing work?
        elif "self-healing" in lower_msg or "how does" in lower_msg or "loop work" in lower_msg or "react" in lower_msg:
            reply = (
                "### 🔄 The Autonomous Self-Healing Reflection Loop\n\n"
                "Unlike traditional autocomplete systems that guess tokens blindly, our agent executes a grounded **ReAct & Reflexion framework**:\n\n"
                "1. **Isolated Subprocess Sandbox:** The synthesized code and pytest suite run inside an ephemeral workspace jail with a 15-second timeout.\n"
                "2. **Deterministic Feedback Ingestion:** The agent captures stdout/stderr, exit codes, and Flake8 linter warnings.\n"
                "3. **Diagnostic Reflection:** If tests fail, the `SelfHealingReflector` produces a structured diagnosis:\n"
                "   - *Root Cause Diagnosis*\n"
                "   - *Flawed Assumptions Identified*\n"
                "   - *Prescribed Corrective Action*\n"
                "4. **Targeted Patch Generation:** The `CodeSynthesizer` receives this diagnosis to generate a repaired patch diff.\n"
                "5. **Convergence:** The loop repeats until all tests pass ($V(s) = 1$) or max iterations are reached."
            )
            reasoning = "Summarized formal ReAct and Reflexion loop mechanics and execution containment."

        # 3. Refactor this function to be faster
        elif "refactor" in lower_msg or "faster" in lower_msg or "optimize" in lower_msg or "performance" in lower_msg:
            reply = (
                "### ⚡ Algorithmic Refactoring & Optimization Strategies\n\n"
                "Here are proven techniques to accelerate this implementation:\n\n"
                "1. **Data Structure Upgrade ($O(N) \\to O(1)$):**\n"
                "   - Replace `list.remove()` or linear lookups with `collections.OrderedDict` or doubly-linked list nodes with a hash map.\n"
                "2. **Monotonic Clocks for High-Precision Timing:**\n"
                "   - Use `time.monotonic()` instead of `time.time()`. Monotonic clocks are immune to wall-clock time adjustments and NTP sync drift.\n"
                "3. **Memory Optimization via `__slots__`:**\n"
                "   - For node-heavy data structures, define `__slots__ = ('key', 'val', 'prev', 'next')` to prevent `__dict__` memory allocation overhead:\n\n"
                "```python\nclass FastCacheNode:\n    __slots__ = ('key', 'value', 'prev', 'next')\n    def __init__(self, key, value):\n        self.key = key\n        self.value = value\n```"
            )
            reasoning = "Synthesized computational complexity reductions ($O(N) \\to O(1)$) and memory optimization patterns."

        # 4. AST Security & Guardrails
        elif "security" in lower_msg or "ast" in lower_msg or "guardrail" in lower_msg:
            reply = (
                "### 🛡️ AST Static Analysis & Security Guardrails\n\n"
                "Before code is written to disk or executed in a subprocess, it undergoes static AST inspection:\n\n"
                "- **`SEC-001` (Banned Imports):** Blocks `subprocess`, `socket`, `ctypes`, `pty`, and `winreg`.\n"
                "- **`SEC-002` (Dynamic Code Execution):** Blocks `eval()`, `exec()`, `compile()`, and `__import__()`.\n"
                "- **`SEC-003` (Dangerous Syscalls):** Intercepts `os.system()`, `os.popen()`, `os.kill()`, and arbitrary filesystem deletion.\n\n"
                "If violations are found, execution halts immediately with exit code `126`, guaranteeing defense-in-depth."
            )
            reasoning = "Explained Abstract Syntax Tree traversal rules and compile-time isolation bounds."

        # 5. Default / General CS & Agent Query
        else:
            reply = (
                f"### 🤖 Agent Copilot Response\n\n"
                f"You asked: *\"{user_message}\"*\n\n"
                f"**Current Status:** Objective: **{objective}** | State: **{ctx.get('status', 'IDLE')}**\n\n"
                f"I am your paired software engineering assistant. You can prompt me anytime to:\n"
                f"- **Explain this bug** to analyze test failures and failed assertions.\n"
                f"- **How does the self-healing loop work?** to learn about ReAct & Reflexion.\n"
                f"- **Refactor this function to be faster** for $O(1)$ complexity enhancements.\n"
                f"- **Explain AST security rules** to review sandbox guardrails."
            )
            reasoning = "Provided contextual guidance and interactive feature discovery."

        return {
            "reply": reply,
            "reasoning": reasoning,
            "fallback_active": False,
            "fallback_message": "",
        }


def get_llm_provider(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> BaseLLMProvider:
    """Factory function to instantiate the appropriate LLM provider with resilient fallback.

    Precedence:
    1. Explicit provider_name if specified.
    2. GEMINI_API_KEY if present -> GeminiProvider (gemini-1.5-flash) with FallbackLLMProvider.
    3. OPENAI_API_KEY if present -> OpenAIProvider (gpt-4o-mini) with FallbackLLMProvider.
    4. OfflineSimulationProvider as zero-cost default.
    """
    choice = (provider_name or os.getenv("LLM_PROVIDER", "")).lower()
    offline_sim = OfflineSimulationProvider()

    if choice == "gemini" or (not choice and os.getenv("GEMINI_API_KEY")):
        key = api_key or os.getenv("GEMINI_API_KEY")
        if key:
            m = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            gemini = GeminiProvider(api_key=key, model=m)
            logger.info(f"Initialized GeminiProvider ({m}) with automatic Fallback failover.")
            return FallbackLLMProvider(primary=gemini, fallback=offline_sim)

    if choice == "openai" or (not choice and os.getenv("OPENAI_API_KEY")):
        key = api_key or os.getenv("OPENAI_API_KEY")
        if key:
            m = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            openai = OpenAIProvider(api_key=key, model=m)
            logger.info(f"Initialized OpenAIProvider ({m}) with automatic Fallback failover.")
            return FallbackLLMProvider(primary=openai, fallback=offline_sim)

    logger.info("Using OfflineSimulationProvider for deterministic demonstration.")
    return offline_sim
