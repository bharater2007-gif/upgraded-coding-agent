"""Academic Benchmark Scenarios for Evaluating Coding Agent Evolution.

Includes test suites with deliberate initial flaws to measure self-healing recovery.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class BenchmarkCase:
    name: str
    category: str
    objective: str
    expected_failures_at_start: List[str]


BENCHMARK_SUITE: List[BenchmarkCase] = [
    BenchmarkCase(
        name="LRU_Cache_Eviction",
        category="Data Structures & Algorithms",
        objective="Design an LRU Cache with capacity limit, O(1) get/put operations, and eviction verification.",
        expected_failures_at_start=["test_eviction_order"],
    ),
    BenchmarkCase(
        name="Rate_Limiter_Refill",
        category="Concurrency & Systems",
        objective="Implement a Token Bucket Rate Limiter with continuous fractional refills and thread safety.",
        expected_failures_at_start=["test_refill_mechanism"],
    ),
    BenchmarkCase(
        name="Fibonacci_Boundary_Guard",
        category="Defensive Programming",
        objective="Implement an optimized Fibonacci generator with negative input exception guards and memoization.",
        expected_failures_at_start=["test_fibonacci_base", "test_fibonacci_negative"],
    ),
]
