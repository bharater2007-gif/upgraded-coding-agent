"""Unit tests for isolated pytest execution engine."""

import tempfile
from pathlib import Path

from sandbox.test_runner import PytestRunner


def test_pytest_runner_passing_suite():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        sol = tmp_path / "solution.py"
        sol.write_text("def multiply(x, y): return x * y\n", encoding="utf-8")

        test_file = tmp_path / "test_solution.py"
        test_file.write_text(
            "from solution import multiply\n"
            "def test_multiply(): assert multiply(3, 4) == 12\n",
            encoding="utf-8",
        )

        runner = PytestRunner(workspace_dir=tmp_path, timeout_seconds=10.0)
        exit_code, stdout, stderr, duration, outcomes = runner.run_tests("test_solution.py")

        assert exit_code == 0
        assert len(outcomes) >= 1
        assert outcomes[0].status == "PASSED"
        assert outcomes[0].name == "test_multiply"


def test_pytest_runner_failing_suite():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        sol = tmp_path / "solution.py"
        sol.write_text("def subtract(x, y): return x + y\n", encoding="utf-8")  # Bug

        test_file = tmp_path / "test_solution.py"
        test_file.write_text(
            "from solution import subtract\n"
            "def test_subtract(): assert subtract(10, 4) == 6\n",
            encoding="utf-8",
        )

        runner = PytestRunner(workspace_dir=tmp_path, timeout_seconds=10.0)
        exit_code, stdout, stderr, duration, outcomes = runner.run_tests("test_solution.py")

        assert exit_code != 0
        assert len(outcomes) >= 1
        assert outcomes[0].status == "FAILED"
        assert outcomes[0].error_message is not None
