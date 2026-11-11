"""Unit tests for Flake8 linter integration."""

from sandbox.linter import run_flake8_on_code


def test_clean_pep8_code_passes():
    clean_code = '''"""Sample module."""


def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b
'''
    report = run_flake8_on_code(clean_code)
    assert report.passed is True
    assert len(report.violations) == 0


def test_linter_flags_unused_import():
    dirty_code = '''"""Module with unused import."""

import math


def hello():
    return "world"
'''
    report = run_flake8_on_code(dirty_code)
    assert report.passed is False
    assert any(v.code.startswith("F401") for v in report.violations)
