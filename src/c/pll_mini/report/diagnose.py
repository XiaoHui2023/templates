from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class DiagnosticIssue:
    """带公式与路径上下文的诊断。"""

    headline: str
    formula: str
    detail: str
    path_nodes: tuple[str, ...] = ()


def diagnostic_from_verify(issue) -> DiagnosticIssue:
    """转换公式回放问题。"""
    return DiagnosticIssue(
        issue.headline, issue.formula, issue.detail, issue.path_nodes
    )


def format_verify_issues(issues) -> str:
    """列出全部回放错误及涉及路径。"""
    return "\n".join(
        f"[verify] {item.headline}\n  {item.formula}\n  {item.detail}\n  path: {' -> '.join(item.path_nodes)}"
        for item in issues
    )


def print_diagnostic_report(tree, *, issues, **kwargs) -> None:
    """输出插件无关的回放错误。"""
    print(format_verify_issues(issues), file=sys.stderr)
