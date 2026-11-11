"""Self-Healing / Reflection Engine.

Analyzes execution logs, pytest tracebacks, and Flake8 linter violations to formulate
root-cause hypotheses, pinpoint flawed assumptions, and synthesize corrective actions.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from agent.llm_provider import BaseLLMProvider
from agent.models import ExecutionResult, ReflectionRecord

logger = logging.getLogger("Agent.Reflector")

REFLECTOR_SYSTEM_PROMPT = """You are an Autonomous Self-Healing AI Diagnostic Engine.
Your responsibility is rigorous root-cause analysis of code failures, failed unit tests,
and static analysis violations.

Inspect the provided code, failed pytest tracebacks, and linter warnings.
Identify why the code failed, what false assumptions were made, and specify
precise, unambiguous corrective steps for the next code synthesis iteration.

You MUST respond strictly with a valid JSON object matching this schema:
{
  "root_cause": "Precise technical explanation of the failure or bug",
  "flawed_assumptions": [
    "Assumption 1 that proved incorrect",
    "Assumption 2 that overlooked an edge condition"
  ],
  "corrective_action": "Clear instructions on how the code must be revised to fix the failure",
  "code_changes_needed": "Specific function or line-level changes required"
}
"""


class SelfHealingReflector:
    """Diagnoses execution failures and produces actionable ReflectionRecords."""

    def __init__(self, llm_provider: BaseLLMProvider):
        self.llm = llm_provider

    def reflect(
        self,
        objective: str,
        code: str,
        test_code: str,
        execution_result: ExecutionResult,
        iteration: int,
    ) -> ReflectionRecord:
        """Perform diagnostic reflection on execution results."""
        # Collate failure signals
        failed_tests = [t for t in execution_result.tests if t.status in ("FAILED", "ERROR")]
        failure_details: List[str] = []

        for ft in failed_tests:
            err = ft.error_message or "Unknown failure"
            failure_details.append(f"Test '{ft.name}' failed:\n{err}")

        linter_issues = []
        if execution_result.linter_report and execution_result.linter_report.violations:
            for v in execution_result.linter_report.violations:
                linter_issues.append(f"Line {v.line}, Col {v.column}: [{v.code}] {v.message}")

        prompt = (
            f"EXECUTION FAILURE REFLECTION (Iteration #{iteration})\n\n"
            f"OBJECTIVE:\n{objective}\n\n"
            f"CURRENT CODE:\n```python\n{code}\n```\n\n"
            f"TEST SUITE:\n```python\n{test_code}\n```\n\n"
            f"PYTEST STDOUT/STDERR:\n{execution_result.stdout}\n{execution_result.stderr}\n\n"
            f"FAILED TEST TRACEBACKS:\n"
            f"{chr(10).join(failure_details) if failure_details else 'None reported'}\n\n"
            f"FLAKE8 LINTER VIOLATIONS:\n"
            f"{chr(10).join(linter_issues) if linter_issues else 'None reported'}\n\n"
            f"Please conduct an in-depth self-reflection analysis and output the JSON diagnosis."
        )

        response_text = self.llm.generate(
            prompt=prompt,
            system_instruction=REFLECTOR_SYSTEM_PROMPT,
            temperature=0.2,
            json_mode=True,
        )

        data = self._parse_json_response(response_text, execution_result, iteration)
        return ReflectionRecord(
            iteration=iteration,
            root_cause=data.get("root_cause", "Execution failed test assertions."),
            flawed_assumptions=data.get("flawed_assumptions", ["Assumed unverified input constraints"]),
            corrective_action=data.get("corrective_action", "Refactor logic to satisfy failing unit tests."),
            code_changes_needed=data.get("code_changes_needed", "Correct boundary and edge-case behavior."),
        )

    def _parse_json_response(
        self, text: str, execution_result: ExecutionResult, iteration: int
    ) -> Dict[str, Any]:
        """Parse LLM JSON diagnosis with regex fallback."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)

        try:
            return json.loads(cleaned)
        except Exception:
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except Exception:
                    pass

        # Robust heuristic fallback based on execution logs
        err_hint = execution_result.stderr or execution_result.stdout or "Test assertion failure"
        return {
            "root_cause": f"Observed failure during iteration {iteration}: {err_hint[:180]}",
            "flawed_assumptions": [
                "Assumed prior implementation covered edge cases",
                "Overlooked strict Flake8 or pytest constraints",
            ],
            "corrective_action": "Fix failing assertion logic and eliminate linter infractions.",
            "code_changes_needed": "Review test criteria and update solution implementation.",
        }
