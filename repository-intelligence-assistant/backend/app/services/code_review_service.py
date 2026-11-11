import ast
import re
from pathlib import Path

from app.services.code_intelligence_service import _read_source
from app.services.dependency_service import list_source_files


def _finding(
    severity: str,
    file_path: str,
    line: int,
    title: str,
    description: str,
    suggestion: str,
) -> dict:
    return {
        "severity": severity,
        "confidence": "Potential concern; confirm against runtime inputs and intended behavior.",
        "file_path": file_path,
        "start_line": line,
        "end_line": line,
        "title": title,
        "description": description,
        "suggestion": suggestion,
        "status": "Potential",
    }


class _PythonReviewVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.findings: list[dict] = []

    def visit_Call(self, node: ast.Call) -> None:
        called = node.func.id if isinstance(node.func, ast.Name) else (
            node.func.attr if isinstance(node.func, ast.Attribute) else ""
        )
        if called in {"eval", "exec"}:
            self.findings.append(_finding(
                "Medium",
                self.file_path,
                node.lineno,
                f"Dynamic code execution via {called}",
                f"`{called}` executes code dynamically. This becomes risky if its input can be influenced by untrusted data; static analysis cannot determine that data flow here.",
                "Avoid dynamic execution where possible; otherwise strictly validate inputs and constrain the execution environment.",
            ))
        if called in {"run", "Popen", "call", "check_call", "check_output"} and any(
            keyword.arg == "shell"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        ):
            self.findings.append(_finding(
                "High",
                self.file_path,
                node.lineno,
                "Subprocess uses a shell",
                "Shell execution can permit command injection when command values contain untrusted input. This check does not establish that the arguments are externally controlled.",
                "Prefer argument-list subprocess calls with `shell=False`; validate any values that must be interpolated.",
            ))
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None or (
            isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"}
        ):
            if any(isinstance(statement, ast.Pass) for statement in node.body):
                self.findings.append(_finding(
                    "Medium",
                    self.file_path,
                    node.lineno,
                    "Broad exception is silently ignored",
                    "A broad exception handler with `pass` can hide failures and make incorrect behavior difficult to diagnose.",
                    "Catch the expected exception types and log, propagate, or handle failures explicitly.",
                ))
        self.generic_visit(node)


def analyze_code_review(repository_root: Path) -> list[dict]:
    findings = []
    for path in list_source_files(repository_root):
        relative = path.relative_to(repository_root).as_posix()
        source = _read_source(path)
        if source is None:
            continue
        if path.suffix.lower() == ".py":
            try:
                visitor = _PythonReviewVisitor(relative)
                visitor.visit(ast.parse(source, filename=relative))
                findings.extend(visitor.findings)
            except SyntaxError as error:
                findings.append(_finding(
                    "Medium",
                    relative,
                    error.lineno or 1,
                    "Python syntax error",
                    f"The file could not be parsed: {error.msg}. Runtime behavior and further static findings in this file could not be checked.",
                    "Correct the syntax error and rerun the review.",
                ))
        else:
            checks = (
                (
                    re.compile(r"\beval\s*\("),
                    "Medium",
                    "Dynamic code execution via eval",
                    "`eval` executes an expression dynamically. It can be unsafe when given untrusted input; this check cannot establish input provenance.",
                    "Avoid `eval` or strictly validate and constrain the evaluated input.",
                ),
                (
                    re.compile(r"\.innerHTML\s*="),
                    "Medium",
                    "HTML assigned through innerHTML",
                    "Assigning HTML directly can create cross-site scripting risk if untrusted content reaches this value; this static check cannot establish that data flow.",
                    "Prefer textContent or a vetted HTML sanitizer when HTML rendering is required.",
                ),
                (
                    re.compile(r"\bcatch\s*(?:\([^)]*\))?\s*\{\s*\}"),
                    "Low",
                    "Exception is silently ignored",
                    "An empty catch block discards an error and may conceal failed operations.",
                    "Handle the expected failure explicitly or log useful diagnostic context.",
                ),
            )
            for line_number, line in enumerate(source.splitlines(), start=1):
                for pattern, severity, title, description, suggestion in checks:
                    if pattern.search(line):
                        findings.append(_finding(
                            severity,
                            relative,
                            line_number,
                            title,
                            description,
                            suggestion,
                        ))
    findings.sort(key=lambda item: (
        {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}.get(item["severity"], 4),
        item["file_path"],
        item["start_line"],
    ))
    return findings
