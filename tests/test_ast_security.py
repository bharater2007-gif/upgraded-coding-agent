"""Unit tests for AST Security Guardrail."""

from sandbox.ast_security import scan_code_security


def test_safe_code_passes():
    safe_code = """
import math
from typing import List

def calculate_mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
"""
    report = scan_code_security(safe_code)
    assert report.passed is True
    assert len(report.violations) == 0
    assert report.scanned_nodes > 0


def test_banned_import_subprocess():
    unsafe_code = """
import subprocess

def run_cmd():
    subprocess.run(["ls", "-la"])
"""
    report = scan_code_security(unsafe_code)
    assert report.passed is False
    assert any("subprocess" in v.message for v in report.violations)


def test_banned_import_socket():
    unsafe_code = """
from socket import socket, AF_INET, SOCK_STREAM

def connect():
    s = socket(AF_INET, SOCK_STREAM)
"""
    report = scan_code_security(unsafe_code)
    assert report.passed is False
    assert any("socket" in v.message for v in report.violations)


def test_banned_eval_call():
    unsafe_code = """
def execute_dynamic(user_input: str):
    return eval(user_input)
"""
    report = scan_code_security(unsafe_code)
    assert report.passed is False
    assert any("eval" in v.message for v in report.violations)


def test_restricted_os_system():
    unsafe_code = """
import os

def delete_all():
    os.system("rm -rf /tmp")
"""
    report = scan_code_security(unsafe_code)
    assert report.passed is False
    assert any("os.system" in v.message for v in report.violations)


def test_syntax_error_handling():
    invalid_code = "def broken_func(:\n    pass"
    report = scan_code_security(invalid_code)
    assert report.passed is False
    assert any("SEC-000-SYNTAX-ERROR" == v.rule for v in report.violations)
