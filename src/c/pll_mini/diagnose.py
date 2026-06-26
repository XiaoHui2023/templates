from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from nodes import (
    ClkNode,
    DivNode,
    GateNode,
    MuxNode,
    PllNode,
    Tree,
    parse_source_endpoint,
)
from reg_paths import CPU_GATE_PASS_THROUGH_GROUP

from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich.tree import Tree

_FREQ_TOL_DEN = 100


@dataclass(frozen=True)
class DebugIssue:
    """一条调试说明。"""

    headline: str
    detail: str


def _freq_tolerance_bounds(
    period_tolerance: float,
) -> tuple[int, int, int]:
    tol_num = round(period_tolerance * _FREQ_TOL_DEN)
    return _FREQ_TOL_DEN - tol_num, _FREQ_TOL_DEN + tol_num, _FREQ_TOL_DEN


def _hz_mhz(hz: int) -> str:
    if hz % 1_000_000 == 0:
        return f"{hz // 1_000_000} MHz"
    if hz % 1_000 == 0:
        return f"{hz / 1_000:.3f} kHz"
    return f"{hz} Hz"


def _yaml_freq(name: str) -> str:
    return f"tree.nodes.{name}.freq"


def _yaml_ratio(name: str) -> str:
    return f"tree.nodes.{name}.ratio"


def _yaml_mux_sel(name: str) -> str:
    return f"tree.nodes.{name}.sel"


def _div_ratio_works(
    in_hz: int,
    out_hz: int,
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
        if freq_hw <= 0:
            continue
        if (
            out_hz * tol_lo <= freq_hw * tol_den
            and out_hz * tol_hi >= freq_hw * tol_den
        ):
            return True
    return False


def _div_output_bands(
    in_hz: int,
    ratio: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> List[tuple[int, int, int]]:
    """返回若干 (freq_hw, out_min_hz, out_max_hz)。"""
    bands: List[tuple[int, int, int]] = []
    for rem in range(ratio):
        hw_num = in_hz - rem
        if hw_num <= 0 or hw_num % ratio != 0:
            continue
        freq_hw = hw_num // ratio
        if freq_hw <= 0:
            continue
        out_min = (freq_hw * tol_den + tol_hi - 1) // tol_hi
        out_max = (freq_hw * tol_den) // tol_lo
        bands.append((freq_hw, out_min, out_max))
    return bands


def _ratio_candidates(div: DivNode) -> List[int]:
    if div.ratio is not None:
        return [div.ratio]
    if div.div_kind in ("div", "div_n", "div_r"):
        return list(range(1, 65))
    if div.div_kind in ("dto", "dto_n"):
        return list(range(2, 65))
    if div.div_kind == "cpu_gate":
        return [2, 3, 4, 6]
    return []


def _nearest_ratio_examples(
    in_hz: int,
    want_out_hz: int,
    candidates: Sequence[int],
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
    *,
    limit: int = 4,
) -> List[str]:
    scored: List[tuple[int, int, int, int]] = []
    for ratio in candidates:
        for rem in range(ratio):
            hw_num = in_hz - rem
            if hw_num <= 0 or hw_num % ratio != 0:
                continue
            freq_hw = hw_num // ratio
            if freq_hw <= 0:
                continue
            err = abs(freq_hw - want_out_hz)
            scored.append((err, ratio, freq_hw, rem))
    scored.sort(key=lambda item: item[0])
    lines: List[str] = []
    seen: set[tuple[int, int]] = set()
    for _err, ratio, freq_hw, rem in scored:
        key = (ratio, freq_hw)
        if key in seen:
            continue
        seen.add(key)
        ok = _div_ratio_works(
            in_hz, want_out_hz, ratio, tol_lo, tol_hi, tol_den
        )
        mark = "可满足" if ok else "仍超出容差"
        rem_note = f"，余数 rem={rem}" if rem else ""
        lines.append(
            f"分频比 {ratio} -> 输出约 {_hz_mhz(freq_hw)}{rem_note}（{mark}）"
        )
        if len(lines) >= limit:
            break
    return lines


def _mux_selected_upstream(
    mux: MuxNode,
    mux_name: str,
) -> str | None:
    """mux 已固定 sel 时返回选中分支的前级节点名；否则返回 None。"""
    if mux.sel is None:
        return None
    key = str(mux.sel)
    arm_ref = mux.source.get(key)
    if not arm_ref:
        return None
    arm_name, _ = parse_source_endpoint(
        arm_ref, ctx=f"mux {mux_name!r} sel {key}"
    )
    return arm_name


def _walk_upstream_chain(tree: Tree, start: str) -> List[str]:
    chain = [start]
    name = start
    seen = {start}
    while True:
        node = tree.nodes[name]
        if node.kind == "source":
            break
        if isinstance(node, MuxNode):
            arm_name = _mux_selected_upstream(node, name)
            if arm_name is None or arm_name in seen:
                break
            seen.add(arm_name)
            chain.append(arm_name)
            name = arm_name
            continue
        parent_name, _out_group = parse_source_endpoint(
            node.source, ctx=f"回溯 {name!r} source"
        )
        if parent_name in seen:
            break
        parent = tree.nodes[parent_name]
        if isinstance(parent, MuxNode):
            seen.add(parent_name)
            chain.append(parent_name)
            arm_name = _mux_selected_upstream(parent, parent_name)
            if arm_name is None or arm_name in seen:
                break
            seen.add(arm_name)
            chain.append(arm_name)
            name = arm_name
            continue
        seen.add(parent_name)
        chain.append(parent_name)
        name = parent_name
    return chain


def _fixed_hz(node: object) -> int | None:
    if getattr(node, "kind", None) == "source":
        freq = getattr(node, "freq", 0)
        return int(freq) if freq > 0 else None
    if isinstance(node, PllNode):
        return node.freq
    if isinstance(node, ClkNode) and node.freq is not None:
        return node.freq
    return None


def _is_passthrough_kind(kind: str) -> bool:
    return kind in ("gate", "inv", "cell", "clk")


def _kind_tag(node: object) -> str:
    if isinstance(node, DivNode):
        return node.div_kind
    if isinstance(node, MuxNode):
        return "mux"
    return str(getattr(node, "kind", "?"))


def _node_state_label(node: object) -> str:
    kind = getattr(node, "kind", None)
    if kind == "source":
        freq = getattr(node, "freq", 0)
        if freq > 0:
            return f"固定 {_hz_mhz(int(freq))}"
        return "频率未固定"
    if isinstance(node, PllNode):
        return f"固定 {_hz_mhz(node.freq)}"
    if isinstance(node, ClkNode):
        if node.freq is not None:
            return f"目标固定 {_hz_mhz(node.freq)}"
        return "频率未固定"
    if isinstance(node, DivNode):
        if node.ratio is not None:
            return f"分频比固定 {node.ratio}"
        return f"分频比未固定（{_allowed_ratio_text(node)}）"
    if isinstance(node, MuxNode):
        if node.sel is not None:
            return f"sel 固定 {node.sel}"
        return "sel 未固定"
    if isinstance(node, GateNode):
        if node.open is not None:
            return "固定开" if node.open else "固定关"
        return "开关未固定"
    if kind in ("gate", "inv", "cell"):
        return "透传，频率未固定"
    return "频率未固定"


def _fixed_badges(node: object) -> List[tuple[str, str]]:
    badges: List[tuple[str, str]] = []
    kind = getattr(node, "kind", None)
    if kind == "source":
        freq = getattr(node, "freq", 0)
        if freq > 0:
            badges.append(("freq", _hz_mhz(int(freq))))
    elif isinstance(node, PllNode):
        badges.append(("target", _hz_mhz(node.freq)))
    elif isinstance(node, ClkNode) and node.freq is not None:
        badges.append(("target", _hz_mhz(node.freq)))
    elif isinstance(node, DivNode):
        if node.ratio is not None:
            badges.append(("ratio", str(node.ratio)))
        elif node.div_kind in ("div", "div_n", "div_r"):
            badges.append(("ratio", "1..64"))
        elif node.div_kind in ("dto", "dto_n"):
            badges.append(("ratio", "2..2^25"))
        elif node.div_kind == "cpu_gate":
            badges.append(("ratio", "2/3/4/6"))
        else:
            badges.append(("ratio", "solver"))
    elif isinstance(node, MuxNode):
        badges.append(("sel", str(node.sel) if node.sel is not None else "auto"))
    elif isinstance(node, GateNode):
        if node.open is None:
            badges.append(("open", "auto"))
        else:
            badges.append(("open", "1" if node.open else "0"))
    return badges


def _node_plain_label(
    name: str,
    node: object,
    *,
    problem_nodes: set[str],
) -> str:
    mark = "! " if name in problem_nodes else ""
    badges = " ".join(f"{key}={value}" for key, value in _fixed_badges(node))
    suffix = f"  {badges}" if badges else ""
    return f"{mark}{name} [{_kind_tag(node)}]{suffix}"


def _source_parent_edges(tree: Tree) -> dict[str, List[tuple[str, str]]]:
    edges: dict[str, List[tuple[str, str]]] = {name: [] for name in tree.nodes}
    for child_name, child in tree.nodes.items():
        if child.kind == "source":
            continue
        if isinstance(child, MuxNode):
            for key, ref in child.source.items():
                parent_name, _ = parse_source_endpoint(
                    ref, ctx=f"mux {child_name!r}"
                )
                edge_label = f"sel={key}"
                if child.sel is not None:
                    edge_label += " *" if str(child.sel) == str(key) else ""
                edges.setdefault(parent_name, []).append((child_name, edge_label))
            continue
        parent_name, out_group = parse_source_endpoint(
            child.source, ctx=f"node {child_name!r} source"
        )
        edge_label = f"[{out_group}]" if out_group else ""
        edges.setdefault(parent_name, []).append((child_name, edge_label))
    for children in edges.values():
        children.sort(key=lambda item: item[0])
    return edges


def _graph_roots(tree: Tree, edges: dict[str, List[tuple[str, str]]]) -> List[str]:
    has_parent = {child for children in edges.values() for child, _ in children}
    roots = [
        name
        for name, node in tree.nodes.items()
        if node.kind == "source" or name not in has_parent
    ]
    return sorted(dict.fromkeys(roots))


def _problem_nodes_from_issues(issues: Sequence[DebugIssue]) -> set[str]:
    problem_nodes: set[str] = set()
    for issue in issues:
        if issue.headline.startswith("div "):
            parts = issue.headline.split()
            if len(parts) >= 2:
                problem_nodes.add(parts[1])
    return problem_nodes


def _plain_tree_graph(
    tree: Tree,
    *,
    issues: Sequence[DebugIssue],
) -> str:
    edges = _source_parent_edges(tree)
    roots = _graph_roots(tree, edges)
    problem_nodes = _problem_nodes_from_issues(issues)
    lines = ["pll_mini diagnose", "clock tree"]

    def walk(
        name: str,
        *,
        prefix: str,
        branch: str,
        seen: set[str],
        edge_label: str = "",
    ) -> None:
        node = tree.nodes[name]
        edge = f"({edge_label}) " if edge_label else ""
        lines.append(
            f"{prefix}{branch}{edge}"
            f"{_node_plain_label(name, node, problem_nodes=problem_nodes)}"
        )
        if name in seen:
            lines[-1] += "  (cycle)"
            return
        next_seen = {*seen, name}
        children = edges.get(name, [])
        for idx, (child, child_edge) in enumerate(children):
            is_last = idx + 1 == len(children)
            child_branch = "`-- " if is_last else "+-- "
            if not branch:
                next_prefix = ""
            elif branch == "`-- ":
                next_prefix = "    "
            else:
                next_prefix = "|   "
            child_prefix = prefix + next_prefix
            walk(
                child,
                prefix=child_prefix,
                branch=child_branch,
                seen=next_seen,
                edge_label=child_edge,
            )

    for root in roots:
        walk(root, prefix="", branch="", seen=set())
    lines.extend(
        [
            "",
            "legend:",
            "  freq            input source fixed frequency",
            "  target          PLL/clk target frequency",
            "  ratio/sel/open  fixed value or auto-solved",
            "  !               divider constraint suspect",
        ]
    )
    return "\n".join(lines)


_DIAG_CONSOLE: Console | None = None


def _diagnostic_console() -> Console:
    global _DIAG_CONSOLE
    if _DIAG_CONSOLE is None:
        _DIAG_CONSOLE = Console(
            stderr=True,
            color_system="truecolor",
            force_terminal=True,
            legacy_windows=False,
        )
    return _DIAG_CONSOLE


def _node_rich_label(
    name: str,
    node: object,
    *,
    problem_nodes: set[str],
) -> Text:
    label = Text()
    if name in problem_nodes:
        label.append("! ", style="bold red")
    label.append(name, style="bold")
    label.append(f" [{_kind_tag(node)}]", style="dim cyan")
    for key, value in _fixed_badges(node):
        label.append(f" {key}=", style="dim")
        label.append(value, style="yellow")
    return label


def _append_tree_children(
    branch: Tree,
    name: str,
    *,
    tree: Tree,
    edges: dict[str, List[tuple[str, str]]],
    problem_nodes: set[str],
    seen: set[str],
) -> None:
    for child_name, edge_label in edges.get(name, []):
        if child_name in seen:
            branch.add(Text("(cycle)", style="dim"))
            continue
        child_node = tree.nodes[child_name]
        label = _node_rich_label(
            child_name,
            child_node,
            problem_nodes=problem_nodes,
        )
        if edge_label:
            label = Text.assemble(
                ("(", "dim"),
                (edge_label, "cyan"),
                (") ", "dim"),
                label,
            )
        child_branch = branch.add(label)
        _append_tree_children(
            child_branch,
            child_name,
            tree=tree,
            edges=edges,
            problem_nodes=problem_nodes,
            seen=seen | {child_name},
        )


def build_clock_tree_rich(
    tree: Tree,
    *,
    issues: Sequence[DebugIssue],
) -> Tree:
    edges = _source_parent_edges(tree)
    roots = _graph_roots(tree, edges)
    problem_nodes = _problem_nodes_from_issues(issues)
    header = Tree(Text.assemble(("时钟树 ", "bold cyan"), (tree.name, "bold white")))
    for root in roots:
        node = tree.nodes[root]
        branch = header.add(
            _node_rich_label(root, node, problem_nodes=problem_nodes)
        )
        _append_tree_children(
            branch,
            root,
            tree=tree,
            edges=edges,
            problem_nodes=problem_nodes,
            seen={root},
        )
    return header


def _diagnostic_legend() -> Panel:
    body = (
        "freq            输入源固定频率\n"
        "target          PLL/clk 目标频率\n"
        "ratio/sel/open  固定值或由求解器决定\n"
        "!               疑似分频约束问题"
    )
    return Panel(body, title="图例", border_style="dim", padding=(0, 1))


def _target_from_div_issue(issue: DebugIssue) -> tuple[str, str] | None:
    if not issue.headline.startswith("div "):
        return None
    parts = issue.headline.split()
    if len(parts) < 2:
        return None
    div_name = parts[1]
    if "->" not in issue.headline:
        return None
    target_name = issue.headline.rsplit("->", 1)[1].strip()
    if not target_name:
        return None
    return div_name, target_name


def _find_downstream_path(tree: Tree, start: str, target: str) -> List[str] | None:
    if start == target:
        return [start]
    parent_of: dict[str, str] = {}
    queue = [start]
    seen = {start}
    while queue:
        name = queue.pop(0)
        for child in _downstream_nodes(tree, name):
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


def _full_path_source_to_target(
    tree: Tree,
    *,
    via: str,
    target: str,
) -> List[str]:
    up_chain = _walk_upstream_chain(tree, via)
    up_path = list(reversed(up_chain))
    down_path = _find_downstream_path(tree, via, target)
    if down_path is None:
        return up_path
    if len(down_path) > 1:
        return up_path + down_path[1:]
    return up_path


def _node_panel_body(
    name: str,
    node: object,
    *,
    problem_nodes: set[str],
) -> str:
    lines = [f"[{_kind_tag(node)}]", _node_state_label(node)]
    badges = _fixed_badges(node)
    if badges:
        lines.append(" ".join(f"{key}={value}" for key, value in badges))
    title = f"! {name}" if name in problem_nodes else name
    return "\n".join([title, *lines])


def build_focus_path_groups(
    tree: Tree,
    *,
    issues: Sequence[DebugIssue],
) -> Group | None:
    problem_nodes = _problem_nodes_from_issues(issues)
    blocks: List[object] = []
    for issue in issues:
        target = _target_from_div_issue(issue)
        if target is None:
            continue
        div_name, target_name = target
        if div_name not in tree.nodes or target_name not in tree.nodes:
            continue
        path = _full_path_source_to_target(
            tree, via=div_name, target=target_name
        )
        if not path:
            continue
        flow: List[object] = [
            Rule(
                Text.assemble(
                    ("路径 ", "cyan"),
                    (path[0], "bold"),
                    (" → ", "dim"),
                    (path[-1], "bold"),
                ),
                style="cyan",
            )
        ]
        for index, node_name in enumerate(path):
            node = tree.nodes[node_name]
            border = "red" if node_name in problem_nodes else "blue"
            flow.append(
                Panel(
                    _node_panel_body(
                        node_name,
                        node,
                        problem_nodes=problem_nodes,
                    ),
                    border_style=border,
                    padding=(0, 1),
                )
            )
            if index + 1 < len(path):
                flow.append(Text("  ↓", style="dim"))
        blocks.append(Group(*flow))
    return Group(*blocks) if blocks else None


def build_debug_issues_rich(
    issues: Sequence[DebugIssue],
) -> Group | None:
    if not issues:
        return None
    panels: List[Panel] = []
    for index, issue in enumerate(issues, start=1):
        border = "red" if issue.headline.startswith("div ") else "yellow"
        panels.append(
            Panel(
                issue.detail,
                title=f"[{index}] {issue.headline}",
                border_style=border,
                padding=(0, 1),
            )
        )
    return Group(*panels)


def build_diagnostic_renderable(
    tree: Tree,
    *,
    issues: Sequence[DebugIssue],
    unsat_core: str = "",
) -> Group:
    parts: List[object] = [
        Rule("[bold]pll_mini 诊断[/bold]", style="cyan"),
    ]
    core_text = unsat_core.strip()
    if core_text:
        parts.append(
            Panel(core_text, title="冲突约束", border_style="red", padding=(0, 1))
        )
    parts.append(build_clock_tree_rich(tree, issues=issues))
    focus = build_focus_path_groups(tree, issues=issues)
    if focus is not None:
        parts.append(focus)
    issue_panels = build_debug_issues_rich(issues)
    if issue_panels is not None:
        parts.append(Rule("调试建议", style="cyan"))
        parts.append(issue_panels)
    parts.append(_diagnostic_legend())
    return Group(*parts)


def print_diagnostic_report(
    tree: Tree,
    *,
    issues: Sequence[DebugIssue],
    unsat_core: str = "",
) -> None:
    """把彩色诊断图输出到 stderr。"""
    _diagnostic_console().print(
        build_diagnostic_renderable(
            tree,
            issues=issues,
            unsat_core=unsat_core,
        )
    )


def format_clock_tree_diagnostic_graph(
    tree: Tree,
    *,
    issues: Sequence[DebugIssue],
) -> str:
    """纯文本回退，供无终端环境或验收调用。"""
    try:
        capture_console = Console(width=100, legacy_windows=False)
        with capture_console.capture() as capture:
            capture_console.print(build_clock_tree_rich(tree, issues=issues))
            capture_console.print(_diagnostic_legend())
        return capture.get().rstrip()
    except Exception:
        return _plain_tree_graph(tree, issues=issues)


def format_debug_issues_summary(issues: Sequence[DebugIssue]) -> str:
    if not issues:
        return ""
    lines = [f"[{index}] {issue.headline}" for index, issue in enumerate(issues, 1)]
    return "调试建议：\n" + "\n".join(lines)


def _format_route_tree(
    tree: Tree,
    path: Sequence[str],
    *,
    highlight: str | None = None,
    route_label: str,
) -> str:
    if not path:
        return ""
    lines = [route_label]
    for depth, name in enumerate(path):
        node = tree.nodes[name]
        indent = "   " * depth
        branch = "`-- " if depth > 0 else ""
        mark = " <- 分频无法满足" if name == highlight else ""
        lines.append(
            f"{indent}{branch}{name} [{_kind_tag(node)}] "
            f"{_node_state_label(node)}{mark}"
        )
    return "\n".join(lines)


def _issue_passthrough_freq_mismatch(
    clk_name: str,
    clk_hz: int,
    pll_name: str,
    pll_hz: int,
    between: Sequence[str],
) -> DebugIssue:
    mid = "、".join(between) if between else "无"
    detail = (
        f"节点 {clk_name} 要求 {_hz_mhz(clk_hz)}，"
        f"同一路径上 pll {pll_name} 固定 {_hz_mhz(pll_hz)}；"
        f"中间 {mid} 只透传频率，两处数值必须相同。"
    )
    return DebugIssue(
        headline=f"透传路径频率不一致：{clk_name} 与 {pll_name}",
        detail=detail,
    )


def _issue_div_impossible(
    tree: Tree,
    div_name: str,
    div: DivNode,
    parent_name: str,
    parent_hz: int,
    child_name: str,
    child_hz: int,
    period_tolerance: float,
) -> DebugIssue:
    tol_lo, tol_hi, tol_den = _freq_tolerance_bounds(period_tolerance)
    tol_pct = period_tolerance * 100
    candidates = _ratio_candidates(div)
    ratio_label = (
        f"固定分频比 {div.ratio}"
        if div.ratio is not None
        else _allowed_ratio_text(div)
    )

    detail_lines = [
        f"div {div_name}（{div.div_kind}，{ratio_label}）",
        f"在容差 {tol_pct:g}% 下，前级通过该 div 分频后够不到下游目标。",
    ]

    path = _full_path_source_to_target(
        tree, via=div_name, target=child_name
    )
    if path:
        detail_lines.append(
            _format_route_tree(
                tree,
                path,
                highlight=div_name,
                route_label=(
                    f"完整路线（{path[0]} -> {path[-1]}）："
                ),
            )
        )
    else:
        detail_lines.extend(
            [
                f"前级 {parent_name} = {_hz_mhz(parent_hz)}",
                f"下游 {child_name} 需要 {_hz_mhz(child_hz)}",
            ]
        )

    if div.ratio is not None:
        bands = _div_output_bands(
            parent_hz, div.ratio, tol_lo, tol_hi, tol_den
        )
        if bands:
            band_text = "；".join(
                f"freq_hw={_hz_mhz(hw)} 时输出 {_hz_mhz(lo)}～{_hz_mhz(hi)}"
                for hw, lo, hi in bands[:3]
            )
            detail_lines.append(
                f"在分频比 {div.ratio} 下，可达输出范围为：{band_text}。"
            )
    else:
        near = _nearest_ratio_examples(
            parent_hz,
            child_hz,
            candidates[:64] if len(candidates) > 64 else candidates,
            tol_lo,
            tol_hi,
            tol_den,
        )
        if near:
            detail_lines.append("接近目标的分频比举例：")
            detail_lines.extend(f"  - {line}" for line in near)

    ideal = parent_hz / child_hz if child_hz > 0 else 0
    if ideal >= 1:
        detail_lines.append(
            f"理想整数比约为 {ideal:.4g}（{parent_name} / {child_name}），"
            f"但受分频比范围与容差约束。"
        )

    return DebugIssue(
        headline=f"div {div_name} 分频无法满足：{path[0] if path else parent_name} -> {child_name}",
        detail="\n".join(detail_lines),
    )


def _allowed_ratio_text(div: DivNode) -> str:
    if div.div_kind in ("div", "div_n", "div_r"):
        return "分频比允许 1～64"
    if div.div_kind in ("dto", "dto_n"):
        return "分频比允许 2～2^25"
    if div.div_kind == "cpu_gate":
        return "分频比只能是 2、3、4、6"
    return "分频比由求解器选取"


def _downstream_nodes(tree: Tree, name: str) -> List[str]:
    children: List[str] = []
    for other_name, other in tree.nodes.items():
        if other_name == name:
            continue
        if isinstance(other, MuxNode):
            for arm_ref in other.source.values():
                arm_name, _ = parse_source_endpoint(
                    arm_ref, ctx=f"downstream mux {other_name!r}"
                )
                if arm_name == name:
                    children.append(other_name)
            continue
        if other.kind == "source":
            continue
        parent_name, _ = parse_source_endpoint(
            other.source, ctx=f"downstream {other_name!r}"
        )
        if parent_name == name:
            children.append(other_name)
    return children


def _can_reach_downstream(tree: Tree, start: str, target: str) -> bool:
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
        for child in _downstream_nodes(tree, name):
            if child not in seen:
                stack.append(child)
    return False


def _collect_clk_targets(tree: Tree) -> List[tuple[str, int]]:
    out: List[tuple[str, int]] = []
    for name, node in tree.nodes.items():
        if isinstance(node, ClkNode) and node.freq is not None:
            out.append((name, node.freq))
    return out


def _collect_div_issues(
    tree: Tree,
    period_tolerance: float,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> List[DebugIssue]:
    issues: List[DebugIssue] = []
    for div_name, div in tree.nodes.items():
        if not isinstance(div, DivNode):
            continue
        parent_name, out_group = parse_source_endpoint(
            div.source, ctx=f"div {div_name!r} source"
        )
        if (
            div.div_kind == "cpu_gate"
            and out_group == CPU_GATE_PASS_THROUGH_GROUP
        ):
            continue
        parent_hz = _fixed_hz(tree.nodes[parent_name])
        if parent_hz is None:
            sub = _walk_upstream_chain(tree, parent_name)
            for n in sub:
                parent_hz = _fixed_hz(tree.nodes[n])
                if parent_hz is not None:
                    break
        if parent_hz is None:
            continue

        for clk_name, clk_hz in _collect_clk_targets(tree):
            if not _can_reach_downstream(tree, div_name, clk_name):
                continue
            if div.ratio is not None:
                ok = _div_ratio_works(
                    parent_hz, clk_hz, div.ratio, tol_lo, tol_hi, tol_den
                )
            else:
                ok = any(
                    _div_ratio_works(
                        parent_hz, clk_hz, ratio, tol_lo, tol_hi, tol_den
                    )
                    for ratio in _ratio_candidates(div)[:64]
                )
            if ok:
                continue
            issues.append(
                _issue_div_impossible(
                    tree,
                    div_name,
                    div,
                    parent_name,
                    parent_hz,
                    clk_name,
                    clk_hz,
                    period_tolerance,
                )
            )
    return issues


def verify_upstream_diagnose(tree: Tree, period_tolerance: float) -> None:
    """供 example + jinja_build 验收；mux 等多路前级回溯与调试诊断不得抛异常。"""
    format_upstream_paths(tree)
    issues = collect_debug_issues(tree, period_tolerance)
    format_clock_tree_diagnostic_graph(tree, issues=issues)


def collect_debug_issues(
    tree: Tree,
    period_tolerance: float,
) -> List[DebugIssue]:
    issues: List[DebugIssue] = []
    tol_lo, tol_hi, tol_den = _freq_tolerance_bounds(period_tolerance)

    for clk_name, clk in tree.nodes.items():
        if not isinstance(clk, ClkNode) or clk.freq is None:
            continue
        clk_hz = clk.freq
        chain = _walk_upstream_chain(tree, clk_name)

        for pll_name in chain:
            pll = tree.nodes[pll_name]
            if not isinstance(pll, PllNode):
                continue
            if pll.freq == clk_hz:
                continue
            idx_clk = chain.index(clk_name)
            idx_pll = chain.index(pll_name)
            between = chain[idx_clk + 1 : idx_pll]
            if between and not all(
                _is_passthrough_kind(tree.nodes[n].kind) for n in between
            ):
                continue
            issues.append(
                _issue_passthrough_freq_mismatch(
                    clk_name, clk_hz, pll_name, pll.freq, between
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
            arm_name, _ = parse_source_endpoint(
                arm_ref, ctx=f"mux {mux_name!r}"
            )
            arm_chain = _walk_upstream_chain(tree, arm_name)
            arm_hz = _fixed_hz(tree.nodes[arm_name])
            if arm_hz is None:
                for n in arm_chain:
                    arm_hz = _fixed_hz(tree.nodes[n])
                    if arm_hz is not None:
                        break
            if arm_hz is not None and arm_hz != clk_hz:
                idx_mux = chain.index(mux_name)
                after_mux = chain[:idx_mux]
                if all(
                    _is_passthrough_kind(tree.nodes[n].kind) for n in after_mux
                ):
                    issues.append(
                        DebugIssue(
                            headline=(
                                f"mux {mux_name} 选中分支与 clk 目标不一致"
                            ),
                            detail=(
                                f"mux {mux_name} 固定 sel={mux.sel}，"
                                f"选中前级 {arm_name} 分支可达 {_hz_mhz(arm_hz)}；"
                                f"但 {clk_name} 要求 {_hz_mhz(clk_hz)}，"
                                f"中间 {', '.join(after_mux) or '无'} 只透传。"
                            ),
                        )
                    )

    issues.extend(
        _collect_div_issues(tree, period_tolerance, tol_lo, tol_hi, tol_den)
    )

    return _dedupe_issues(issues)


def _dedupe_issues(issues: Sequence[DebugIssue]) -> List[DebugIssue]:
    seen: set[str] = set()
    out: List[DebugIssue] = []
    for item in issues:
        key = item.headline
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def format_debug_issues(issues: Sequence[DebugIssue]) -> str:
    if not issues:
        return ""
    blocks: List[str] = []
    for index, issue in enumerate(issues, start=1):
        blocks.append(
            f"[{index}] {issue.headline}\n"
            f"  {issue.detail.replace(chr(10), chr(10) + '  ')}"
        )
    return "调试建议：\n" + "\n\n".join(blocks)


def format_upstream_paths(tree: Tree) -> str:
    lines: List[str] = []
    for name, node in tree.nodes.items():
        if node.kind != "clk":
            continue
        chain = _walk_upstream_chain(tree, name)
        parts: List[str] = []
        for n in chain:
            nd = tree.nodes[n]
            suffix = ""
            hz = _fixed_hz(nd)
            if hz is not None:
                suffix = f" [{_hz_mhz(hz)}]"
            elif isinstance(nd, DivNode) and nd.ratio is not None:
                suffix = f" [ratio={nd.ratio}]"
            elif isinstance(nd, MuxNode) and nd.sel is not None:
                suffix = f" [sel={nd.sel}]"
            parts.append(f"{n}{suffix}")
        lines.append(f"- {' <- '.join(parts)}")
    if not lines:
        return ""
    return "\n".join(lines)


def format_node_path_cheatsheet(tree: Tree) -> str:
    lines: List[str] = []
    for name, node in tree.nodes.items():
        if node.kind == "source" and node.freq > 0:
            lines.append(f"- {_yaml_freq(name)} = {node.freq}")
        elif isinstance(node, PllNode):
            lines.append(f"- {_yaml_freq(name)} = {node.freq}")
        elif isinstance(node, ClkNode) and node.freq is not None:
            lines.append(f"- {_yaml_freq(name)} = {node.freq}")
        elif isinstance(node, DivNode) and node.ratio is not None:
            lines.append(f"- {_yaml_ratio(name)} = {node.ratio}")
        elif isinstance(node, MuxNode) and node.sel is not None:
            lines.append(f"- {_yaml_mux_sel(name)} = {node.sel}")
        elif isinstance(node, GateNode) and node.open is not None:
            lines.append(f"- tree.nodes.{name}.open = {int(node.open)}")
    if not lines:
        return ""
    return "\n".join(lines)
