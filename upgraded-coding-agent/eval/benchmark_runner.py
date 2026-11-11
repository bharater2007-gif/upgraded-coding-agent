"""Academic Evaluation Harness: Baseline (Zero-Shot) vs. Upgraded Self-Healing Agent.

Quantitatively evaluates Pass@1 vs. Pass@N self-healing recovery rates,
Flake8 style remediation, and convergence latency across benchmark cases.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Add parent directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agent.models import TaskStatus
from agent.orchestrator import AgentOrchestrator
from eval.scenarios import BENCHMARK_SUITE, BenchmarkCase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Eval.BenchmarkRunner")


def evaluate_system(max_retries: int = 4) -> Dict[str, Any]:
    """Execute comparative benchmark comparing Zero-Shot to Self-Healing."""
    results: List[Dict[str, Any]] = []

    logger.info("Starting Academic Benchmark Evaluation...")

    for case in BENCHMARK_SUITE:
        logger.info(f"Evaluating Scenario: {case.name} [{case.category}]")
        orch = AgentOrchestrator()

        # Disable HITL for unattended automated benchmarking
        state = orch.create_task(
            objective=case.objective,
            require_hitl=False,
            max_iterations=max_retries,
        )

        start_time = time.perf_counter()

        # Step 1: Planning
        orch.step(state.task_id)

        # Step 2: Initial Code Synthesis
        orch.step(state.task_id)

        # Step 3: AST Security Audit
        orch.step(state.task_id)

        # Step 4: First execution (Zero-Shot Baseline)
        orch.step(state.task_id)
        zero_shot_passed = state.execution_result.success if state.execution_result else False
        zero_shot_tests_passed = (
            sum(1 for t in state.execution_result.tests if t.status == "PASSED")
            if state.execution_result
            else 0
        )
        total_tests = len(state.execution_result.tests) if state.execution_result else 0

        # Run remaining self-healing iterations if failed
        if not zero_shot_passed:
            orch.run_until_stop(state.task_id)

        duration = time.perf_counter() - start_time
        final_state = orch.get_task(state.task_id)

        final_passed = final_state.status == TaskStatus.COMPLETED
        iterations_used = final_state.current_iteration
        reflections_count = len(final_state.reflections)

        flake8_violations = (
            len(final_state.execution_result.linter_report.violations)
            if final_state.execution_result and final_state.execution_result.linter_report
            else 0
        )

        case_result = {
            "case_name": case.name,
            "category": case.category,
            "zero_shot_passed": zero_shot_passed,
            "zero_shot_score": f"{zero_shot_tests_passed}/{total_tests}",
            "self_healed_passed": final_passed,
            "iterations_used": iterations_used,
            "reflections_count": reflections_count,
            "flake8_violations": flake8_violations,
            "duration_seconds": round(duration, 3),
        }
        results.append(case_result)
        logger.info(f"Finished {case.name}: Healed={final_passed} in {iterations_used} iterations.")

    # Calculate aggregate metrics
    total_cases = len(results)
    zero_shot_successes = sum(1 for r in results if r["zero_shot_passed"])
    self_heal_successes = sum(1 for r in results if r["self_healed_passed"])

    report = {
        "summary": {
            "total_benchmark_cases": total_cases,
            "zero_shot_pass_rate": f"{(zero_shot_successes / total_cases) * 100:.1f}%",
            "self_healing_pass_rate": f"{(self_heal_successes / total_cases) * 100:.1f}%",
            "recovery_gain": f"{((self_heal_successes - zero_shot_successes) / total_cases) * 100:.1f}%",
        },
        "detailed_results": results,
    }

    return report


if __name__ == "__main__":
    rep = evaluate_system()
    print("\n" + "=" * 60)
    print("ACADEMIC BENCHMARK RESULTS SUMMARY")
    print("=" * 60)
    print(json.dumps(rep, indent=2))
