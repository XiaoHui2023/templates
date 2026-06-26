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
from rich.tree import Tree as RichTree

_FREQ_TOL_DEN = 100


@dataclass(frozen=True)
class DebugIssue:
    """一条调试说明。"""

    headline: str
    detail: str
    path_nodes: tuple[str, ...] = ()


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


def _problem_nodes_from_issues(issues: Sequence[DebugIssue]) -> set[str]:
    problem_nodes: set[str] = set()
    for issue in issues:
        if issue.headline.startswith("div "):
            parts = issue.headline.split()
            if len(parts) >= 2:
                problem_nodes.add(parts[1])
    return problem_nodes


def _plain_path_graph(
    tree: Tree,
    path_nodes: Sequence[str],
    *,
    issues: Sequence[DebugIssue],
) -> str:
    if not path_nodes:
        return ""
    problem_nodes = _problem_nodes_from_issues(issues)
    lines = ["相关路径:"]
    for index, name in enumerate(path_nodes):
        node = tree.nodes[name]
        if index == 0:
            lines.append(
                _node_plain_label(name, node, problem_nodes=problem_nodes)
            )
            continue
        indent = "    " * (index - 1)
        lines.append(
            f"{indent}`-- "
            f"{_node_plain_label(name, node, problem_nodes=problem_nodes)}"
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


def build_path_clock_tree_rich(
    tree: Tree,
    path_nodes: Sequence[str],
    *,
    issues: Sequence[DebugIssue],
) -> RichTree | None:
    if not path_nodes:
        return None
    problem_nodes = _problem_nodes_from_issues(issues)
    root_name = path_nodes[0]
    root = RichTree(
        Text("相关路径", style="bold cyan"),
        guide_style="dim",
    )
    branch = root.add(
        _node_rich_label(
            root_name,
            tree.nodes[root_name],
            problem_nodes=problem_nodes,
        )
    )
    for name in path_nodes[1:]:
        branch = branch.add(
            _node_rich_label(
                name,
                tree.nodes[name],
                problem_nodes=problem_nodes,
            )
        )
    return root


def _diagnostic_legend() -> Panel:
    body = (
        "freq            输入源固定频率\n"
        "target          PLL/clk 目标频率\n"
        "ratio/sel/open  固定值或由求解器决定\n"
        "!               疑似分频约束问题"
    )
    return Panel(body, title="图例", border_style="dim", padding=(0, 1))


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


def format_clock_tree_plain(
    tree: Tree,
    *,
    issues: Sequence[DebugIssue],
) -> str:
    """仅输出与错误相关的路径子树，供错误正文与无 Rich 环境使用。"""
    if not issues:
        return ""
    blocks: List[str] = []
    for issue in issues:
        if not issue.path_nodes:
            continue
        block = _plain_path_graph(tree, issue.path_nodes, issues=issues)
        if block:
            blocks.append(block)
    return "\n\n".join(blocks)


def build_debug_issues_rich(
    tree: Tree,
    issues: Sequence[DebugIssue],
) -> Group | None:
    if not issues:
        return None
    panels: List[Panel] = []
    for index, issue in enumerate(issues, start=1):
        border = "red" if issue.headline.startswith("div ") else "yellow"
        body_parts: List[object] = []
        path_tree = build_path_clock_tree_rich(
            tree,
            issue.path_nodes,
            issues=issues,
        )
        if path_tree is not None:
            body_parts.append(path_tree)
        body_parts.append(issue.detail)
        panels.append(
            Panel(
                Group(*body_parts),
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
    issue_panels = build_debug_issues_rich(tree, issues)
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
    if not issues:
        return ""
    try:
        capture_console = Console(width=100, legacy_windows=False)
        with capture_console.capture() as capture:
            issue_panels = build_debug_issues_rich(tree, issues)
            if issue_panels is not None:
                capture_console.print(issue_panels)
                capture_console.print(_diagnostic_legend())
        return capture.get().rstrip()
    except Exception:
        return format_clock_tree_plain(tree, issues=issues)


def format_debug_issues_summary(issues: Sequence[DebugIssue]) -> str:
    if not issues:
        return ""
    lines = [f"[{index}] {issue.headline}" for index, issue in enumerate(issues, 1)]
    return "调试建议：\n" + "\n".join(lines)


def _issue_passthrough_freq_mismatch(
    clk_name: str,
    clk_hz: int,
    pll_name: str,
    pll_hz: int,
    between: Sequence[str],
    *,
    path_nodes: Sequence[str],
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
        path_nodes=tuple(path_nodes),
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
    *,
    required_out_hz: int | None = None,
) -> DebugIssue:
    tol_lo, tol_hi, tol_den = _freq_tolerance_bounds(period_tolerance)
    tol_pct = period_tolerance * 100
    candidates = _ratio_candidates(div)
    ratio_label = (
        f"固定分频比 {div.ratio}"
        if div.ratio is not None
        else _allowed_ratio_text(div)
    )
    want_out_hz = (
        required_out_hz if required_out_hz is not None else child_hz
    )

    detail_lines = [
        f"div {div_name}（{div.div_kind}，{ratio_label}）",
        f"在容差 {tol_pct:g}% 下，前级通过该 div 分频后够不到下游目标。",
    ]
    if required_out_hz is not None and required_out_hz != child_hz:
        detail_lines.append(
            f"通过下游分频后 {child_name} 需要 {_hz_mhz(child_hz)}，"
            f"该 div 输出应约为 {_hz_mhz(required_out_hz)}。"
        )

    path = _full_path_source_to_target(
        tree, via=div_name, target=child_name
    )
    if not path:
        detail_lines.extend(
            [
                f"前级 {parent_name} = {_hz_mhz(parent_hz)}",
                f"下游 {child_name} 需要 {_hz_mhz(want_out_hz)}",
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
            want_out_hz,
            candidates[:64] if len(candidates) > 64 else candidates,
            tol_lo,
            tol_hi,
            tol_den,
        )
        if near:
            detail_lines.append("接近目标的分频比举例：")
            detail_lines.extend(f"  - {line}" for line in near)

    ideal = parent_hz / want_out_hz if want_out_hz > 0 else 0
    if ideal >= 1:
        detail_lines.append(
            f"理想整数比约为 {ideal:.4g}（{parent_name} 到该 div 输出），"
            f"但受分频比范围与容差约束。"
        )

    return DebugIssue(
        headline=f"div {div_name} 分频无法满足：{path[0] if path else parent_name} -> {child_name}",
        detail="\n".join(detail_lines),
        path_nodes=tuple(path),
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


def _div_on_selected_mux_path(
    tree: Tree,
    div_name: str,
    clk_name: str,
) -> bool:
    """div 在到达 clk 的路径上，且未被固定 sel 的 mux 排除在未选中分支时返回真。"""
    path = _find_downstream_path(tree, div_name, clk_name)
    if not path:
        return False
    for mux_name in path:
        if mux_name == div_name:
            continue
        mux = tree.nodes.get(mux_name)
        if not isinstance(mux, MuxNode) or mux.sel is None:
            continue
        sel_key = str(mux.sel)
        arm_ref = mux.source.get(sel_key)
        if not arm_ref:
            return False
        arm_name, _ = parse_source_endpoint(
            arm_ref, ctx=f"mux {mux_name!r} sel {sel_key}"
        )
        arm_chain = _walk_upstream_chain(tree, arm_name)
        if div_name not in arm_chain and div_name != arm_name:
            return False
    return True


def _required_hz_at_node_output(
    tree: Tree,
    *,
    node_name: str,
    clk_name: str,
    clk_hz: int,
) -> int | None:
    """从 clk 目标反推 node 输出应达到的理想频率；下游含未固定 ratio 的 div 时返回 None。"""
    path = _find_downstream_path(tree, node_name, clk_name)
    if path is None or node_name not in path:
        return None
    node_idx = path.index(node_name)
    required = clk_hz
    for i in range(len(path) - 1, node_idx, -1):
        downstream = path[i]
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


def _pll_to_clk_path_nodes(
    chain: Sequence[str],
    *,
    clk_name: str,
    pll_name: str,
) -> tuple[str, ...]:
    idx_clk = chain.index(clk_name)
    idx_pll = chain.index(pll_name)
    between = chain[idx_clk + 1 : idx_pll]
    path = list(reversed(chain[idx_pll:])) + list(reversed(between)) + [clk_name]
    return tuple(path)


def _mux_to_clk_path_nodes(
    tree: Tree,
    *,
    mux_name: str,
    arm_name: str,
    clk_name: str,
) -> tuple[str, ...]:
    chain = _walk_upstream_chain(tree, clk_name)
    idx_mux = chain.index(mux_name)
    down_part = list(reversed(chain[: idx_mux + 1]))
    up_part = list(reversed(_walk_upstream_chain(tree, arm_name)))
    if down_part and up_part:
        return tuple(up_part + down_part[1:])
    if down_part:
        return tuple(down_part)
    return tuple(up_part)


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

        checked_any = False
        satisfiable_any = False
        last_failure: tuple[str, int, int] | None = None
        for clk_name, clk_hz in _collect_clk_targets(tree):
            if not _can_reach_downstream(tree, div_name, clk_name):
                continue
            if not _div_on_selected_mux_path(tree, div_name, clk_name):
                continue
            required_out = _required_hz_at_node_output(
                tree,
                node_name=div_name,
                clk_name=clk_name,
                clk_hz=clk_hz,
            )
            if required_out is None:
                continue
            checked_any = True
            if div.ratio is not None:
                ok = _div_ratio_works(
                    parent_hz,
                    required_out,
                    div.ratio,
                    tol_lo,
                    tol_hi,
                    tol_den,
                )
            else:
                ok = any(
                    _div_ratio_works(
                        parent_hz,
                        required_out,
                        ratio,
                        tol_lo,
                        tol_hi,
                        tol_den,
                    )
                    for ratio in _ratio_candidates(div)[:64]
                )
            if ok:
                satisfiable_any = True
                break
            last_failure = (clk_name, clk_hz, required_out)
        if checked_any and not satisfiable_any and last_failure is not None:
            clk_name, clk_hz, required_out = last_failure
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
                    required_out_hz=required_out,
                )
            )
    return issues


def verify_upstream_diagnose(
    tree: Tree,
    period_tolerance: float,
    *,
    expect_satisfiable: bool = False,
) -> None:
    """供 example + jinja_build 验收；mux 等多路前级回溯与调试诊断不得抛异常。"""
    format_upstream_paths(tree)
    issues = collect_debug_issues(tree, period_tolerance)
    if expect_satisfiable:
        div_issues = [
            issue for issue in issues if issue.headline.startswith("div ")
        ]
        if div_issues:
            raise ValueError(
                "求解已成功但诊断仍报告分频无法满足："
                f"{div_issues[0].headline}"
            )
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
                    clk_name,
                    clk_hz,
                    pll_name,
                    pll.freq,
                    between,
                    path_nodes=_pll_to_clk_path_nodes(
                        chain,
                        clk_name=clk_name,
                        pll_name=pll_name,
                    ),
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
            required_at_mux = _required_hz_at_node_output(
                tree,
                node_name=mux_name,
                clk_name=clk_name,
                clk_hz=clk_hz,
            )
            if arm_hz is not None and required_at_mux is not None:
                mux_ok = _div_ratio_works(
                    arm_hz,
                    required_at_mux,
                    1,
                    tol_lo,
                    tol_hi,
                    tol_den,
                )
                if not mux_ok:
                    issues.append(
                        DebugIssue(
                            headline=(
                                f"mux {mux_name} 选中分支与 clk 目标不一致"
                            ),
                            detail=(
                                f"mux {mux_name} 固定 sel={mux.sel}，"
                                f"选中前级 {arm_name} 分支可达 {_hz_mhz(arm_hz)}；"
                                f"但 {clk_name} 通过下游分频后要求 mux 输出约 "
                                f"{_hz_mhz(required_at_mux)}。"
                            ),
                            path_nodes=_mux_to_clk_path_nodes(
                                tree,
                                mux_name=mux_name,
                                arm_name=arm_name,
                                clk_name=clk_name,
                            ),
                        )
                    )
            elif arm_hz is not None and arm_hz != clk_hz:
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
                            path_nodes=_mux_to_clk_path_nodes(
                                tree,
                                mux_name=mux_name,
                                arm_name=arm_name,
                                clk_name=clk_name,
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
