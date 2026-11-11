"""Autonomous Task Decomposition Engine.

Analyzes high-level software requirements or bug reports and constructs
a structured, test-driven decomposition plan into actionable subtasks.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from agent.llm_provider import BaseLLMProvider
from agent.models import SubTask, TaskPlan

logger = logging.getLogger("Agent.Planner")

PLANNER_SYSTEM_PROMPT = """You are an expert Principal AI Software Architect.
Your role is Autonomous Task Decomposition: dissect complex software objectives, bug fixes,
or architectural requirements into concrete, sequential programming subtasks.
Each subtask must specify its objective and verifiable test criteria.

You MUST respond strictly with a valid JSON object matching this schema:
{
  "rationale": "High-level architectural explanation of the approach",
  "subtasks": [
    {
      "id": "ST-1",
      "title": "Short descriptive title",
      "description": "Concrete technical details of what must be implemented or fixed",
      "test_criteria": ["Specific assertion or test condition to satisfy"]
    }
  ]
}
"""


class TaskPlanner:
    """Decomposes coding objectives into structured SubTasks."""

    def __init__(self, llm_provider: BaseLLMProvider):
        self.llm = llm_provider

    def decompose(self, objective: str) -> TaskPlan:
        """Decompose objective into a verifiable TaskPlan."""
        prompt = (
            f"Decompose the following high-level objective into concrete software engineering subtasks:\n\n"
            f"OBJECTIVE:\n{objective}\n\n"
            f"Ensure subtasks cover core logic, boundary conditions, edge cases, error handling, "
            f"and unit test verification."
        )

        response_text = self.llm.generate(
            prompt=prompt,
            system_instruction=PLANNER_SYSTEM_PROMPT,
            temperature=0.2,
            json_mode=True,
        )

        plan_data = self._parse_json_response(response_text, objective)
        return TaskPlan.from_dict(plan_data)

    def _parse_json_response(self, text: str, objective: str) -> Dict[str, Any]:
        """Safely parse JSON response with regex fallback for markdown code fences."""
        cleaned = text.strip()
        # Remove markdown code fences if present
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as err:
            logger.warning(f"Failed to parse planner JSON directly: {err}. Attempting regex match.")
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except Exception:
                    pass

            # Safe deterministic fallback plan
            return {
                "objective": objective,
                "rationale": "Decompose into architecture setup, core algorithm, edge cases, and test suite.",
                "subtasks": [
                    {
                        "id": "ST-1",
                        "title": "Interface and Type Definitions",
                        "description": "Establish class structures, function signatures, and type annotations.",
                        "test_criteria": ["Type signatures match specifications"],
                    },
                    {
                        "id": "ST-2",
                        "title": "Core Implementation",
                        "description": "Implement primary algorithm and required behaviors.",
                        "test_criteria": ["Standard test cases pass"],
                    },
                    {
                        "id": "ST-3",
                        "title": "Edge Case & Bounds Handling",
                        "description": "Handle boundary conditions, empty collections, and zero values.",
                        "test_criteria": ["Edge-case unit tests pass"],
                    },
                    {
                        "id": "ST-4",
                        "title": "Flake8 & Style Compliance",
                        "description": "Ensure clean PEP8 styling and eliminate linter warnings.",
                        "test_criteria": ["Flake8 reports 0 violations"],
                    },
                ],
            }
