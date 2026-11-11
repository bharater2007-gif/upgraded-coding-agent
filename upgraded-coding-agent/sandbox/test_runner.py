"""Isolated pytest execution engine.

Executes test suites within a controlled workspace directory, captures stdout/stderr,
and parses test outcomes into structured telemetric records.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

from agent.models import TestOutcome


class PytestRunner:
    """Executes pytest in a subprocess sandbox with timeout and telemetry parsing."""

    def __init__(self, workspace_dir: Path, timeout_seconds: float = 15.0):
        self.workspace_dir = workspace_dir
        self.timeout_seconds = timeout_seconds

    def run_tests(self, test_file_name: str = "test_solution.py") -> Tuple[int, str, str, float, List[TestOutcome]]:
        """Run pytest against the target test file inside the workspace.

        Returns: (exit_code, stdout, stderr, duration, List[TestOutcome])
        """
        test_file_path = self.workspace_dir / test_file_name
        if not test_file_path.exists():
            return (
                1,
                "",
                f"Test file not found: {test_file_path}",
                0.0,
                [TestOutcome(name=test_file_name, status="ERROR", error_message="File not found")],
            )

        cache_dir = self.workspace_dir / ".pytest_cache"
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-v",
            "--tb=short",
            f"--rootdir={self.workspace_dir}",
            "-o",
            f"cache_dir={cache_dir}",
            str(test_file_name),
        ]

        # Use an isolated environment with restricted PYTHONPATH
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.workspace_dir)
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        start_time = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.workspace_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env,
            )
            duration = time.perf_counter() - start_time
            outcomes = self._parse_pytest_output(proc.stdout)
            return proc.returncode, proc.stdout, proc.stderr, duration, outcomes

        except subprocess.TimeoutExpired as err:
            duration = time.perf_counter() - start_time
            stdout = err.stdout.decode() if isinstance(err.stdout, bytes) else (err.stdout or "")
            stderr = f"TIMEOUT: Execution exceeded {self.timeout_seconds} seconds limit."
            outcomes = [
                TestOutcome(
                    name=test_file_name,
                    status="FAILED",
                    duration=duration,
                    error_message=stderr,
                )
            ]
            return 124, stdout, stderr, duration, outcomes

        except Exception as exc:
            duration = time.perf_counter() - start_time
            return 1, "", str(exc), duration, [
                TestOutcome(name=test_file_name, status="ERROR", duration=duration, error_message=str(exc))
            ]

    def _parse_pytest_output(self, stdout: str) -> List[TestOutcome]:
        """Extract individual test statuses and assertion errors from pytest output."""
        outcomes: List[TestOutcome] = []
        # Pattern e.g. test_solution.py::test_basic_put_get PASSED
        # Pattern e.g. test_solution.py::test_eviction_order FAILED
        line_pattern = re.compile(r"^(\S+::\S+)\s+(PASSED|FAILED|ERROR|SKIPPED)", re.MULTILINE)

        for match in line_pattern.finditer(stdout):
            test_id, status = match.groups()
            test_name = test_id.split("::")[-1]
            outcomes.append(
                TestOutcome(
                    name=test_name,
                    status=status,
                )
            )

        # Extract failure details
        if "FAILED" in stdout or "ERROR" in stdout:
            # Look for FAILURES section
            failures_section = re.search(r"=+\s+FAILURES\s+=+([\s\S]+?)(?:=+\s+short test summary|$)", stdout)
            if failures_section:
                failure_text = failures_section.group(1).strip()
                # Attach failure text to failed outcomes
                for outcome in outcomes:
                    if outcome.status in ("FAILED", "ERROR"):
                        outcome.error_message = failure_text

        # If no tests matched regex but tests were run or failed early
        if not outcomes:
            if "collected 0 items" in stdout:
                outcomes.append(
                    TestOutcome(
                        name="test_discovery",
                        status="ERROR",
                        error_message="No tests collected by pytest.",
                    )
                )
            elif "syntaxerror" in stdout.lower() or "error" in stdout.lower():
                outcomes.append(
                    TestOutcome(
                        name="test_suite",
                        status="ERROR",
                        error_message="SyntaxError or import error during pytest collection.",
                    )
                )

        return outcomes
