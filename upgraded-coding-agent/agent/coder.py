"""Code Synthesis and Patch Generation Engine.

Synthesizes production-quality Python code and corresponding pytest test suites.
During reflection iterations, incorporates diagnostic feedback to repair bugs
and generates unified diff patches for transparent human inspection.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

from agent.llm_provider import BaseLLMProvider
from agent.models import CodePatch, ReflectionRecord, TaskPlan

logger = logging.getLogger("Agent.Coder")

CODER_INITIAL_SYSTEM_PROMPT = """You are an Autonomous Principal AI Software Engineer.
Your objective is to write production-grade, PEP8-compliant Python code and a thorough pytest suite.
Adhere strictly to:
1. Strict type hinting and clean docstrings.
2. Comprehensive test coverage including happy path and boundary conditions.
3. No forbidden security calls (no subprocess, socket, eval, exec).
4. Full Flake8 compliance (no unused imports, lines <= 100 chars, no trailing spaces).

You MUST respond strictly with a valid JSON object matching this schema:
{
  "code": "Python source code string for solution.py",
  "test_code": "Pytest test code string for test_solution.py",
  "explanation": "Concise summary of the implementation"
}
"""

CODER_HEALING_SYSTEM_PROMPT = """You are an Autonomous Self-Healing AI Software Engineer.
Your objective is to repair a failing implementation based on diagnostic reflection feedback.

You have been provided with:
- The previous implementation code and test suite.
- The root-cause analysis and flawed assumptions identified by the diagnostic reflector.
- Execution errors, pytest tracebacks, and Flake8 violations.

Revise the code so that ALL tests pass without any Flake8 style violations or security breaches.
You MUST respond strictly with a valid JSON object matching this schema:
{
  "code": "Updated, repaired Python source code string for solution.py",
  "test_code": "Updated Pytest test code string for test_solution.py",
  "explanation": "Explanation of the precise bug fix and architectural adjustments"
}
"""


class CodeSynthesizer:
    """Synthesizes code implementations and repairs failing iterations."""

    def __init__(self, llm_provider: BaseLLMProvider):
        self.llm = llm_provider

    def synthesize_initial(
        self,
        objective: str,
        plan: Optional[TaskPlan] = None,
        target_file: str = "solution.py",
        test_file: str = "test_solution.py",
    ) -> Tuple[str, str, CodePatch]:
        """Synthesize initial implementation and unit test suite."""
        plan_desc = ""
        if plan:
            plan_desc = f"\nARCHITECTURAL PLAN:\n{json.dumps(plan.to_dict(), indent=2)}\n"

        prompt = (
            f"OBJECTIVE:\n{objective}\n"
            f"{plan_desc}\n"
            f"Generate target implementation file '{target_file}' and pytest suite '{test_file}'."
        )

        response_text = self.llm.generate(
            prompt=prompt,
            system_instruction=CODER_INITIAL_SYSTEM_PROMPT,
            temperature=0.2,
            json_mode=True,
        )

        data = self._parse_json_response(response_text)
        code = data.get("code", "")
        test_code = data.get("test_code", "")
        explanation = data.get("explanation", "Initial code synthesis.")

        patch = CodePatch(
            file_path=target_file,
            original_code="",
            patched_code=code,
            explanation=explanation,
        )

        return code, test_code, patch

    def synthesize_fix(
        self,
        objective: str,
        current_code: str,
        test_code: str,
        reflection: ReflectionRecord,
        target_file: str = "solution.py",
        test_file: str = "test_solution.py",
    ) -> Tuple[str, str, CodePatch]:
        """Synthesize repaired implementation incorporating reflection diagnostics."""
        prompt = (
            f"SELF-HEALING FIX (Iteration #{reflection.iteration})\n\n"
            f"OBJECTIVE:\n{objective}\n\n"
            f"ROOT CAUSE DIAGNOSIS:\n{reflection.root_cause}\n\n"
            f"FLAWED ASSUMPTIONS IDENTIFIED:\n"
            f"{chr(10).join('- ' + a for a in reflection.flawed_assumptions)}\n\n"
            f"CORRECTIVE ACTION PRESCRIBED:\n{reflection.corrective_action}\n\n"
            f"CURRENT CODE:\n```python\n{current_code}\n```\n\n"
            f"TEST CODE:\n```python\n{test_code}\n```\n\n"
            f"Generate the corrected code that resolves this issue and satisfies all tests."
        )

        response_text = self.llm.generate(
            prompt=prompt,
            system_instruction=CODER_HEALING_SYSTEM_PROMPT,
            temperature=0.2,
            json_mode=True,
        )

        data = self._parse_json_response(response_text)
        new_code = data.get("code", current_code)
        new_test_code = data.get("test_code", test_code)
        explanation = data.get("explanation", f"Self-healing fix for: {reflection.root_cause}")

        patch = CodePatch(
            file_path=target_file,
            original_code=current_code,
            patched_code=new_code,
            explanation=explanation,
        )

        return new_code, new_test_code, patch

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parse LLM JSON response with code block and regex resilience."""
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

        # Fallback empty structure
        return {
            "code": "# Failed to parse code synthesis\n",
            "test_code": "# Failed to parse test synthesis\n",
            "explanation": "Parsing error encountered during synthesis.",
        }
