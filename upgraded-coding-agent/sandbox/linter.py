"""Flake8 integration and code style verification.

Executes Flake8 against target code and returns structured violation reports.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

from agent.models import LinterReport, LinterViolation


def run_flake8_on_file(file_path: Path, max_line_length: int = 100) -> LinterReport:
    """Run flake8 on a given file path and parse structured output."""
    cmd = [
        sys.executable,
        "-m",
        "flake8",
        f"--max-line-length={max_line_length}",
        "--isolated",
        str(file_path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        raw_output = proc.stdout + proc.stderr
        violations: List[LinterViolation] = []

        # Standard Flake8 format: path:line:col: CODE Description (handles Windows C:\ drive paths)
        pattern = re.compile(r"^(.*?):(\d+):(\d+):\s+([A-Z]\d+)\s+(.+)$", re.MULTILINE)
        for match in pattern.finditer(raw_output):
            file_name, line, col, code, message = match.groups()
            violations.append(
                LinterViolation(
                    file=Path(file_name).name,
                    line=int(line),
                    column=int(col),
                    code=code,
                    message=message.strip(),
                )
            )

        passed = len(violations) == 0
        return LinterReport(
            passed=passed,
            violations=violations,
            raw_output=raw_output.strip(),
        )

    except subprocess.TimeoutExpired:
        return LinterReport(
            passed=False,
            violations=[
                LinterViolation(
                    file=file_path.name,
                    line=1,
                    column=1,
                    code="TIMEOUT",
                    message="Flake8 execution timed out.",
                )
            ],
            raw_output="Flake8 execution exceeded 10 second timeout.",
        )
    except Exception as exc:
        return LinterReport(
            passed=False,
            violations=[
                LinterViolation(
                    file=file_path.name,
                    line=1,
                    column=1,
                    code="ERR",
                    message=f"Flake8 execution error: {str(exc)}",
                )
            ],
            raw_output=str(exc),
        )


def run_flake8_on_code(code_str: str, filename: str = "solution.py") -> LinterReport:
    """Run flake8 on in-memory code string via a temporary file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / filename
        tmp_path.write_text(code_str, encoding="utf-8")
        return run_flake8_on_file(tmp_path)
