from __future__ import annotations
from dataclasses import dataclass
from typing import List, Sequence
from .nodes import Tree
from .solve_model import SolveModel
from .freq_graph import Port, collect_freq_targets, walk_path_upstream


@dataclass(frozen=True)
class VerifyIssue:
    headline: str
    formula: str
    detail: str
    path_nodes: tuple[str, ...]


def _hz_mhz(hz: int) -> str:
    if hz % 1_000_000 == 0:
        return f"{hz // 1_000_000} MHz"
    if hz % 1_000 == 0:
        return f"{hz / 1_000:.3f} kHz"
    return f"{hz} Hz"


def _path_for_edge(tree: Tree, child: str, clk_name: str, model=None) -> tuple[str, ...]:
    chain = walk_path_upstream(tree, clk_name, model=model)
    if child in chain:
        idx = chain.index(child)
        return tuple(reversed(chain[idx:]))
    return (child,)


def raise_on_verify_issues(
    tree: Tree,
    issues: Sequence[VerifyIssue],
) -> None:
    if not issues:
        return
    from report.diagnose import (
        diagnostic_from_verify,
        format_verify_issues,
        print_diagnostic_report,
    )

    diag = [diagnostic_from_verify(item) for item in issues]
    print_diagnostic_report(tree, issues=diag)
    text = format_verify_issues(issues)
    raise ValueError(f"{text}\n\n路径子树见 stderr。")


def verify_solve_model(
    tree: Tree, model: SolveModel, *, period_tolerance: float
) -> List[VerifyIssue]:
    """检查目标频率，并调用各插件独立回放公式。"""
    issues = []
    for name, wanted in collect_freq_targets(tree):
        actual = model.port_hz(Port(name))
        if actual != wanted:
            issues.append(
                VerifyIssue(
                    f"nodes[{name!r}].freq 与目标不一致",
                    "f_out = target",
                    f"target={wanted}, model={actual}",
                    (name,),
                )
            )
    for node in tree.nodes_ordered:
        issues.extend(node.verify(tree, model, period_tolerance))
    return issues
