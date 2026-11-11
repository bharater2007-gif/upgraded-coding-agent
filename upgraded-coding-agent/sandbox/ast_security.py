"""AST-based static analyzer for security verification and sandbox guardrails.

Inspects Python AST prior to execution to flag forbidden imports, dangerous builtins,
and high-risk syscalls (e.g., eval, exec, arbitrary subprocesses, socket operations).
"""

from __future__ import annotations

import ast
import time
from typing import List, Set

from agent.models import SecurityReport, SecurityViolation


class ASTSecurityScanner(ast.NodeVisitor):
    """Inspects AST nodes against security guardrails."""

    BANNED_IMPORTS: Set[str] = {
        "subprocess",
        "socket",
        "ctypes",
        "pty",
        "winreg",
        "multiprocessing",
    }

    BANNED_FUNCTIONS: Set[str] = {
        "eval",
        "exec",
        "compile",
        "__import__",
    }

    RESTRICTED_OS_CALLS: Set[str] = {
        "system",
        "popen",
        "spawn",
        "kill",
        "remove",
        "rmdir",
        "unlink",
    }

    def __init__(self):
        super().__init__()
        self.violations: List[SecurityViolation] = []
        self.scanned_nodes: int = 0
        self.scanned_imports: int = 0

    def visit(self, node: ast.AST):
        self.scanned_nodes += 1
        super().visit(node)

    def visit_Import(self, node: ast.Import):
        self.scanned_imports += len(node.names)
        for alias in node.names:
            base_module = alias.name.split(".")[0]
            if base_module in self.BANNED_IMPORTS:
                self.violations.append(
                    SecurityViolation(
                        severity="CRITICAL",
                        rule="SEC-001-BANNED-IMPORT",
                        message=f"Import of forbidden low-level module '{alias.name}' is prohibited.",
                        line_no=node.lineno,
                        node_text=alias.name,
                    )
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        self.scanned_imports += 1
        if node.module:
            base_module = node.module.split(".")[0]
            if base_module in self.BANNED_IMPORTS:
                self.violations.append(
                    SecurityViolation(
                        severity="CRITICAL",
                        rule="SEC-001-BANNED-IMPORT",
                        message=f"Import from forbidden module '{node.module}' is prohibited.",
                        line_no=node.lineno,
                        node_text=node.module,
                    )
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Check direct calls like eval(...) or exec(...)
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in self.BANNED_FUNCTIONS:
                self.violations.append(
                    SecurityViolation(
                        severity="CRITICAL",
                        rule="SEC-002-DYNAMIC-EXEC",
                        message=f"Direct invocation of dynamic code execution function '{func_name}()' is prohibited.",
                        line_no=node.lineno,
                        node_text=func_name,
                    )
                )

        # Check attribute calls like os.system(...)
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in self.RESTRICTED_OS_CALLS:
                # Check if calling on 'os'
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                    self.violations.append(
                        SecurityViolation(
                            severity="CRITICAL",
                            rule="SEC-003-OS-SYSCALL",
                            message=f"High-risk OS syscall 'os.{attr_name}()' is blocked in sandbox.",
                            line_no=node.lineno,
                            node_text=f"os.{attr_name}",
                        )
                    )

        self.generic_visit(node)


def scan_code_security(code: str) -> SecurityReport:
    """Analyze code string using AST security visitor."""
    start_time = time.perf_counter()

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return SecurityReport(
            passed=False,
            violations=[
                SecurityViolation(
                    severity="CRITICAL",
                    rule="SEC-000-SYNTAX-ERROR",
                    message=f"Code fails basic AST parsing: {e.msg}",
                    line_no=e.lineno,
                )
            ],
            scanned_nodes=0,
            scanned_imports=0,
            duration_ms=duration_ms,
        )

    scanner = ASTSecurityScanner()
    scanner.visit(tree)

    duration_ms = (time.perf_counter() - start_time) * 1000.0
    critical_violations = [v for v in scanner.violations if v.severity == "CRITICAL"]
    passed = len(critical_violations) == 0

    return SecurityReport(
        passed=passed,
        violations=scanner.violations,
        scanned_nodes=scanner.scanned_nodes,
        scanned_imports=scanner.scanned_imports,
        duration_ms=duration_ms,
    )
