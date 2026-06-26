from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping, Sequence, Set

from formulas import (
    DTO_MAX_RATIO,
    freq_tolerance_bounds,
    freq_within_tolerance,
)
from freq_model import (
    collect_freq_targets,
    output_ports,
    parent_port_for_child,
    walk_path_upstream,
)
from nodes import (
    ClkNode,
    DivNode,
    MuxNode,
    PllNode,
    Tree,
    parse_source_endpoint,
)
from smt import format_unsat_diagnosis
from tools import log_stage_done, log_stage_start
from verify import VerifyIssue

from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich.tree import Tree as RichTree


@dataclass(frozen=True)
class DiagnosticIssue:
    headline: str
    formula: str
    detail: str
    path_nodes: tuple[str, ...] = ()


def _hz_mhz(hz: int) -> str:
    if hz % 1_000_000 == 0:
        return f"{hz // 1_000_000} MHz"
    if hz % 1_000 == 0:
        return f"{hz / 1_000:.3f} kHz"
    return f"{hz} Hz"


def _ratio_candidates(div: DivNode) -> List[int]:
    if div.ratio is not None:
        return [div.ratio]
    if div.div_kind in ("div", "div_n", "div_r"):
        return list(range(1, 65))
    if div.div_kind in ("dto", "dto_n"):
        return list(range(2, min(65, DTO_MAX_RATIO + 1)))
    if div.div_kind == "cpu_gate":
        return [2, 3, 4, 6]
    return []


def _fixed_hz(tree: Tree, name: str) -> int | None:
    node = tree.nodes[name]
    if node.kind == "source" and node.freq > 0:
        return node.freq
    if isinstance(node, PllNode) and node.freq is not None:
        return node.freq
    if isinstance(node, ClkNode) and node.freq is not None and node.freq > 0:
        return node.freq
    return None


def collect_static_issues(
    tree: Tree,
    period_tolerance: float,
) -> List[DiagnosticIssue]:
    """求解前的静态矛盾检查。"""
    issues: List[DiagnosticIssue] = []
    tol_lo, tol_hi, tol_den = freq_tolerance_bounds(period_tolerance)
    targets = collect_freq_targets(tree)

    for clk_name, clk_hz in targets:
        chain = walk_path_upstream(tree, clk_name)
        for pll_name in chain:
            pll = tree.nodes[pll_name]
            if not isinstance(pll, PllNode):
                continue
            if pll.pll_kind == "inno":
                continue
            if pll.freq is None:
                continue
            if pll.freq == clk_hz:
                continue
            idx_clk = chain.index(clk_name)
            idx_pll = chain.index(pll_name)
            between = chain[idx_clk + 1 : idx_pll]
            if between and not all(
                tree.nodes[n].kind in ("gate", "inv", "cell", "clk")
                for n in between
            ):
                continue
            path = list(reversed(chain[idx_pll:])) + list(
                reversed(between)
            ) + [clk_name]
            issues.append(
                DiagnosticIssue(
                    headline=f"透传路径频率矛盾：{clk_name} 与 {pll_name}",
                    formula="透传节点满足 f_out = f_ref",
                    detail=(
                        f"clk {clk_name} 目标 {_hz_mhz(clk_hz)}，"
                        f"pll {pll_name} 配置 {_hz_mhz(pll.freq)}；"
                        f"中间仅透传，两处必须相同。"
                    ),
                    path_nodes=tuple(path),
                )
            )

        for mux_name in chain:
            mux = tree.nodes[mux_name]
            if not isinstance(mux, MuxNode) or mux.sel is None:
                continue
            key = str(mux.sel)
            arm_ref = mux.source.get(key)
            if not arm_ref:
                continue
            arm_port = parse_source_endpoint(arm_ref, ctx=f"mux {mux_name!r}")
            arm_name = arm_port[0]
            arm_hz = _fixed_hz(tree, arm_name)
            if arm_hz is None:
                continue
            if not freq_within_tolerance(
                clk_hz, arm_hz, tol_lo=tol_lo, tol_hi=tol_hi, tol_den=tol_den
            ):
                path = walk_path_upstream(tree, clk_name)
                issues.append(
                    DiagnosticIssue(
                        headline=f"mux {mux_name} 选中臂与 clk 目标不一致",
                        formula="透传路径上 f_clk 应接近选中臂输出",
                        detail=(
                            f"mux {mux_name} 固定 sel={mux.sel}，"
                            f"臂 {arm_name} 可达 {_hz_mhz(arm_hz)}；"
                            f"clk {clk_name} 要求 {_hz_mhz(clk_hz)}。"
                        ),
                        path_nodes=tuple(path),
                    )
                )

    for div_name, div in tree.nodes.items():
        if not isinstance(div, DivNode):
            continue
        parent_port = parent_port_for_child(tree, div_name)
        parent_hz = _fixed_hz(tree, parent_port.node)
        if parent_hz is None:
            continue
        for clk_name, clk_hz in targets:
            path_down = _downstream_contains(tree, div_name, clk_name)
            if not path_down:
                continue
            required_out = _required_hz_before_clk(
                tree, div_name, clk_name, clk_hz
            )
            if required_out is None:
                continue
            ok = any(
                _div_can_reach(
                    parent_hz,
                    required_out,
                    ratio,
                    tol_lo,
                    tol_hi,
                    tol_den,
                )
                for ratio in _ratio_candidates(div)[:64]
            )
            if not ok:
                path = walk_path_upstream(tree, clk_name)
                if div_name in path:
                    idx = path.index(div_name)
                    path = tuple(reversed(path[idx:])) + (clk_name,)
                issues.append(
                    DiagnosticIssue(
                        headline=f"div {div_name} 无法满足下游 {clk_name}",
                        formula="f_out ≈ f_ref / ratio，ratio 在允许范围内",
                        detail=(
                            f"前级 {_hz_mhz(parent_hz)}，"
                            f"该 div 输出需约 {_hz_mhz(required_out)} "
                            f"才能到达 clk {_hz_mhz(clk_hz)}。"
                        ),
                        path_nodes=path,
                    )
                )
                break

    return _dedupe(issues)


def _downstream_contains(tree: Tree, start: str, target: str) -> bool:
    if start == target:
        return True
    seen: set[str] = set()
    stack = [start]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        if name == target:
            return True
        for child in _children(tree, name):
            stack.append(child)
    return False


def _children(tree: Tree, name: str) -> List[str]:
    out: List[str] = []
    for other_name, other in tree.nodes.items():
        if other_name == name or other.kind == "source":
            continue
        if isinstance(other, MuxNode):
            for arm in other.source.values():
                arm_name, _ = parse_source_endpoint(arm, ctx="child")
                if arm_name == name:
                    out.append(other_name)
            continue
        try:
            parent = parent_port_for_child(tree, other_name)
        except ValueError:
            continue
        if parent.node == name:
            out.append(other_name)
    return out


def _required_hz_before_clk(
    tree: Tree,
    node_name: str,
    clk_name: str,
    clk_hz: int,
) -> int | None:
    path = _find_downstream(tree, node_name, clk_name)
    if path is None:
        return None
    idx = path.index(node_name)
    required = clk_hz
    for downstream in reversed(path[idx + 1 :]):
        node = tree.nodes[downstream]
        if node.kind in ("gate", "inv", "cell", "clk"):
            continue
        if isinstance(node, MuxNode):
            continue
        if isinstance(node, DivNode):
            if node.div_kind == "cpu_gate" or node.ratio is None:
                return None
            required *= node.ratio
            continue
        return None
    return required


def _find_downstream(tree: Tree, start: str, target: str) -> List[str] | None:
    if start == target:
        return [start]
    parent_of: dict[str, str] = {}
    queue = [start]
    seen = {start}
    while queue:
        name = queue.pop(0)
        for child in _children(tree, name):
            if child in seen:
                continue
            seen.add(child)
            parent_of[child] = name
            if child == target:
                path = [target]
                cur = name
                while True:
                    path.append(cur)
                    if cur == start:
                        break
                    cur = parent_of[cur]
                path.reverse()
                return path
            queue.append(child)
    return None


def _div_can_reach(
    in_hz: int,
    want_out: int,
    ratio: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> bool:
    for rem in range(ratio):
        hw_num = in_hz - rem
        if hw_num <= 0 or hw_num % ratio != 0:
            continue
        freq_hw = hw_num // ratio
        if freq_within_tolerance(
            want_out, freq_hw, tol_lo=tol_lo, tol_hi=tol_hi, tol_den=tol_den
        ):
            return True
    return False


def _dedupe(items: Sequence[DiagnosticIssue]) -> List[DiagnosticIssue]:
    seen: set[str] = set()
    out: List[DiagnosticIssue] = []
    for item in items:
        key = item.headline
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def diagnostic_from_verify(issue: VerifyIssue) -> DiagnosticIssue:
    return DiagnosticIssue(
        headline=issue.headline,
        formula=issue.formula,
        detail=issue.detail,
        path_nodes=issue.path_nodes,
    )


def format_verify_issues(issues: Sequence[VerifyIssue]) -> str:
    diag = [diagnostic_from_verify(item) for item in issues]
    return format_diagnostic_issues(diag)


def format_diagnostic_issues(issues: Sequence[DiagnosticIssue]) -> str:
    if not issues:
        return ""
    blocks: List[str] = []
    for index, issue in enumerate(issues, start=1):
        blocks.append(
            f"[{index}] {issue.headline}\n"
            f"  公式：{issue.formula}\n"
            f"  {issue.detail.replace(chr(10), chr(10) + '  ')}"
        )
    return "诊断：\n\n" + "\n\n".join(blocks)


_DIAG_CONSOLE: Console | None = None


def _console() -> Console:
    global _DIAG_CONSOLE
    if _DIAG_CONSOLE is None:
        _DIAG_CONSOLE = Console(
            stderr=True,
            color_system="truecolor",
            force_terminal=True,
            legacy_windows=False,
        )
    return _DIAG_CONSOLE


def _node_label(tree: Tree, name: str, *, mark: bool) -> Text:
    node = tree.nodes[name]
    kind = getattr(node, "kind", "?")
    if isinstance(node, DivNode):
        kind = node.div_kind
    label = Text()
    if mark:
        label.append("! ", style="bold red")
    label.append(name, style="bold")
    label.append(f" [{kind}]", style="dim cyan")
    hz = _fixed_hz(tree, name)
    if hz is not None:
        label.append(f" target={_hz_mhz(hz)}", style="yellow")
    elif isinstance(node, DivNode) and node.ratio is not None:
        label.append(f" ratio={node.ratio}", style="yellow")
    elif isinstance(node, MuxNode) and node.sel is not None:
        label.append(f" sel={node.sel}", style="yellow")
    return label


def build_issue_path_tree(
    tree: Tree,
    path_nodes: Sequence[str],
    *,
    focus: str | None = None,
) -> RichTree | None:
    if not path_nodes:
        return None
    root_name = path_nodes[0]
    root = RichTree(Text("相关路径", style="bold cyan"), guide_style="dim")
    branch = root.add(
        _node_label(tree, root_name, mark=root_name == focus)
    )
    for name in path_nodes[1:]:
        branch = branch.add(_node_label(tree, name, mark=name == focus))
    return root


def print_diagnostic_report(
    tree: Tree,
    *,
    issues: Sequence[DiagnosticIssue],
    unsat_core: str = "",
    headline: str = "",
) -> None:
    from ui import active_progress_session

    session = active_progress_session()
    if session is not None:
        session.failed = True
        session.halt_for_output()
    title = headline.strip() or "pll_mini 诊断"
    parts: List[object] = [Rule(f"[bold]{title}[/bold]", style="cyan")]
    core_text = unsat_core.strip()
    if core_text:
        parts.append(
            Panel(core_text, title="冲突约束", border_style="red", padding=(0, 1))
        )
    for index, issue in enumerate(issues, start=1):
        body: List[object] = []
        path_tree = build_issue_path_tree(
            tree,
            issue.path_nodes,
            focus=issue.path_nodes[-1] if issue.path_nodes else None,
        )
        if path_tree is not None:
            body.append(path_tree)
        body.append(Text(f"公式：{issue.formula}", style="dim"))
        body.append(issue.detail)
        parts.append(
            Panel(
                Group(*body),
                title=f"[{index}] {issue.headline}",
                border_style="red",
                padding=(0, 1),
            )
        )
    _console().print(Group(*parts))


def format_search_component_failure(
    tree: Tree,
    *,
    period_tolerance: float,
    component_index: int,
    component_total: int,
    component_targets: Sequence[tuple[str, int]],
    component_nodes: Set[str],
) -> str:
    """子树定向搜索失败时的静态诊断与路径图。"""
    static_started_at = log_stage_start(
        "diagnose",
        "collect",
        f"component {component_index}/{component_total}",
        clks=len(component_targets),
        nodes=len(component_nodes),
    )
    issues = collect_static_issues(tree, period_tolerance)
    scoped: List[DiagnosticIssue] = []
    for issue in issues:
        if not issue.path_nodes:
            scoped.append(issue)
            continue
        if component_nodes.intersection(issue.path_nodes):
            scoped.append(issue)
    if not scoped:
        scoped = list(issues)
    log_stage_done(
        "diagnose",
        "collect",
        f"component {component_index}/{component_total}",
        static_started_at,
        issues=len(scoped),
    )
    render_started_at = log_stage_start(
        "diagnose",
        "format",
        f"component {component_index}/{component_total}",
        nodes=len(component_nodes),
    )
    clk_list = ", ".join(name for name, _ in component_targets)
    print_diagnostic_report(
        tree,
        issues=scoped,
        headline=(
            f"子树 {component_index}/{component_total} 求解失败"
            f"（clk: {clk_list}）"
        ),
    )
    log_stage_done(
        "diagnose",
        "format",
        f"component {component_index}/{component_total}",
        render_started_at,
        issues=len(scoped),
    )
    detail_text = format_diagnostic_issues(scoped)
    if detail_text:
        return f"{detail_text}\n\n路径子树见 stderr。"
    return ""


def format_solve_failure_detail(
    tree: Tree,
    *,
    period_tolerance: float,
    smt2_named: str,
    hints: Mapping[str, str],
) -> str:
    unsat_started_at = log_stage_start(
        "diagnose",
        "unsat_core",
        "z3 unsat core",
        hints=len(hints),
    )
    core = format_unsat_diagnosis(smt2_named, hints)
    log_stage_done(
        "diagnose",
        "unsat_core",
        "z3 unsat core",
        unsat_started_at,
        found=bool(core),
    )

    static_started_at = log_stage_start(
        "diagnose",
        "collect",
        "static issues",
        nodes=len(tree.nodes),
    )
    issues = collect_static_issues(tree, period_tolerance)
    log_stage_done(
        "diagnose",
        "collect",
        "static issues",
        static_started_at,
        issues=len(issues),
    )

    render_started_at = log_stage_start(
        "diagnose",
        "format",
        "tree graph",
        nodes=len(tree.nodes),
    )
    print_diagnostic_report(tree, issues=issues, unsat_core=core or "")
    log_stage_done(
        "diagnose",
        "format",
        "tree graph",
        render_started_at,
        issues=len(issues),
    )

    detail_text = format_diagnostic_issues(issues)
    if detail_text:
        return f"{detail_text}\n\n路径子树见 stderr。"
    if core:
        return "约束冲突；彩色诊断图已输出到 stderr。"
    return ""


def format_debug_issues(issues: Sequence[DiagnosticIssue]) -> str:
    return format_diagnostic_issues(issues)
