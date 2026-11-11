"""Unit tests for SandboxExecutor."""

from sandbox.executor import SandboxExecutor


def test_executor_passes_clean_code():
    executor = SandboxExecutor()
    code = '''"""Math library."""


def square(x: int) -> int:
    """Return x squared."""
    return x * x
'''
    test_code = '''"""Tests for square."""

from solution import square


def test_square():
    assert square(5) == 25
    assert square(0) == 0
'''
    result = executor.execute_and_test(code, test_code)
    assert result.success is True
    assert result.exit_code == 0
    assert any(t.status == "PASSED" for t in result.tests)


def test_executor_blocks_malicious_code():
    executor = SandboxExecutor()
    code = '''"""Malicious code."""

import subprocess


def exploit():
    subprocess.run(["echo", "hacked"])
'''
    test_code = "def test_noop(): pass\n"
    result = executor.execute_and_test(code, test_code)
    assert result.success is False
    assert result.exit_code == 126
    assert "SECURITY AUDIT FAILED" in result.stderr


def test_executor_timeout_infinite_loop():
    executor = SandboxExecutor(timeout_seconds=2.0)
    code = '''"""Infinite loop."""


def loop_forever():
    while True:
        pass
'''
    test_code = '''"""Tests."""

from solution import loop_forever


def test_loop():
    loop_forever()
'''
    result = executor.execute_and_test(code, test_code)
    assert result.success is False
    assert result.exit_code == 124 or "TIMEOUT" in result.stderr
