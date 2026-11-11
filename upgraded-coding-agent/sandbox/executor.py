"""Unified Execution Sandbox Manager.

Orchestrates AST security verification, linter analysis, and isolated pytest execution
in a dedicated directory sandbox with strict resource limits and timeout handling.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional

from agent.models import ExecutionResult, SecurityReport
from sandbox.ast_security import scan_code_security
from sandbox.linter import run_flake8_on_file
from sandbox.test_runner import PytestRunner

logger = logging.getLogger("Sandbox.Executor")


class SandboxExecutor:
    """Manages isolated code execution, linting, and automated unit testing."""

    def __init__(self, base_sandbox_dir: Optional[Path] = None, timeout_seconds: float = 15.0):
        if base_sandbox_dir:
            self.base_sandbox_dir = base_sandbox_dir
        else:
            self.base_sandbox_dir = Path(__file__).resolve().parent.parent / ".sandboxes"
        self.timeout_seconds = timeout_seconds

    def execute_and_test(
        self,
        code: str,
        test_code: str,
        target_file: str = "solution.py",
        test_file: str = "test_solution.py",
        task_id: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute full verification pipeline:

        1. AST Security Audit (Fails fast if dangerous imports or syscalls are detected).
        2. Workspace Isolation (Writes code & test to temporary isolated jail).
        3. Flake8 Static Analysis (Captures style and linting errors).
        4. Subprocess Pytest Runner (Runs unit tests with strict timeouts).
        """
        start_time = time.perf_counter()

        # Step 1: AST Security Static Analysis
        sec_report: SecurityReport = scan_code_security(code)
        if not sec_report.passed:
            violation_details = "; ".join([f"{v.rule}: {v.message}" for v in sec_report.violations])
            total_duration = time.perf_counter() - start_time
            return ExecutionResult(
                success=False,
                exit_code=126,  # Standard exit code for permission/security rejection
                stdout="",
                stderr=f"SECURITY AUDIT FAILED: {violation_details}",
                duration=total_duration,
                summary=f"Execution blocked by AST Security Guardrail: {violation_details}",
            )

        # Step 2: Create isolated workspace
        if self.base_sandbox_dir:
            self.base_sandbox_dir.mkdir(parents=True, exist_ok=True)
            workspace = Path(tempfile.mkdtemp(prefix=f"jail_{task_id or 'run'}_", dir=self.base_sandbox_dir))
        else:
            workspace = Path(tempfile.mkdtemp(prefix="jail_run_"))

        try:
            target_path = workspace / target_file
            test_path = workspace / test_file

            target_path.write_text(code, encoding="utf-8")
            test_path.write_text(test_code, encoding="utf-8")

            # Step 3: Run Flake8 Linter
            linter_report = run_flake8_on_file(target_path)

            # Step 4: Run Isolated Pytest
            runner = PytestRunner(workspace_dir=workspace, timeout_seconds=self.timeout_seconds)
            exit_code, stdout, stderr, test_duration, test_outcomes = runner.run_tests(test_file)

            total_duration = time.perf_counter() - start_time

            # Determine overall success: tests must pass AND no critical linter/security errors
            tests_passed = exit_code == 0 and len(test_outcomes) > 0 and all(t.status == "PASSED" for t in test_outcomes)
            # We treat test success as primary, and linter warnings as diagnostic
            success = tests_passed

            passed_count = sum(1 for t in test_outcomes if t.status == "PASSED")
            failed_count = sum(1 for t in test_outcomes if t.status in ("FAILED", "ERROR"))

            summary = (
                f"Tests: {passed_count} passed, {failed_count} failed in {test_duration:.2f}s. "
                f"Flake8 violations: {len(linter_report.violations)}."
            )

            return ExecutionResult(
                success=success,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration=total_duration,
                linter_report=linter_report,
                tests=test_outcomes,
                summary=summary,
            )

        finally:
            # Clean up the temporary jail directory
            try:
                shutil.rmtree(workspace, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to clean up workspace {workspace}: {e}")
