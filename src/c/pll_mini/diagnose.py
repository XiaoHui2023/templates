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

_FREQ_TOL_DEN = 100


@dataclass(frozen=True)
class DebugIssue:
    """一条可操作的调试说明。"""

    headline: str
    detail: str
    fixes: tuple[str, ...]


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
            f"分频比 {ratio} → 输出约 {_hz_mhz(freq_hw)}{rem_note}（{mark}）"
        )
        if len(lines) >= limit:
            break
    return lines


def _walk_upstream_chain(tree: Tree, start: str) -> List[str]:
    chain = [start]
    name = start
    seen = {start}
    while True:
        node = tree.nodes[name]
        if node.kind == "source":
            break
        parent_name, _out_group = parse_source_endpoint(
            node.source, ctx=f"回溯 {name!r} source"
        )
        if parent_name in seen:
            break
        parent = tree.nodes[parent_name]
        if isinstance(parent, MuxNode):
            seen.add(parent_name)
            chain.append(parent_name)
            if parent.sel is None:
                break
            key = str(parent.sel)
            arm_ref = parent.source.get(key)
            if not arm_ref:
                break
            arm_name, _ = parse_source_endpoint(
                arm_ref, ctx=f"mux {parent_name!r} sel {key}"
            )
            if arm_name in seen:
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
    fixes = (
        f"把 {_yaml_freq(clk_name)} 改为 {pll_hz}",
        f"或把 {_yaml_freq(pll_name)} 改为 {clk_hz}",
    )
    if between:
        fixes = (
            *fixes,
            f"或在中间插入 div 节点做分频，而不是直接透传",
        )
    return DebugIssue(
        headline=f"透传路径频率不一致：{clk_name} 与 {pll_name}",
        detail=detail,
        fixes=fixes,
    )


def _issue_div_impossible(
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
        f"前级 {parent_name} = {_hz_mhz(parent_hz)}",
        f"下游 {child_name} 需要 {_hz_mhz(child_hz)}",
        f"在容差 {tol_pct:g}% 下，前级通过该 div 分频后够不到下游目标。",
    ]

    fixes: List[str] = []
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
            best_lo, best_hi = bands[0][1], bands[0][2]
            fixes.append(
                f"把 {_yaml_freq(child_name)} 调到 {best_lo}～{best_hi} 之间"
            )
            approx_parent = child_hz * div.ratio
            fixes.append(
                f"或把 {_yaml_freq(parent_name)} 调到约 {approx_parent}"
            )
        fixes.append(f"或删除 {_yaml_ratio(div_name)}，让求解器自动选分频比")
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
            detail_lines.extend(f"  · {line}" for line in near)
            scored: List[tuple[int, int, int]] = []
            for ratio in candidates[:64]:
                for rem in range(ratio):
                    hw_num = parent_hz - rem
                    if hw_num <= 0 or hw_num % ratio != 0:
                        continue
                    freq_hw = hw_num // ratio
                    if freq_hw <= 0:
                        continue
                    scored.append(
                        (abs(freq_hw - child_hz), ratio, freq_hw)
                    )
            if scored:
                _err, best_ratio, best_hw = min(scored, key=lambda item: item[0])
                fixes.insert(
                    0,
                    f"把 {_yaml_freq(child_name)} 改为 {best_hw}"
                    f"（分频比 {best_ratio} 时最接近）",
                )
                fixes.insert(
                    1,
                    f"或把 {_yaml_freq(parent_name)} 改为约 {child_hz * best_ratio}",
                )
        fixes.append(
            f"调整 {_yaml_freq(child_name)} 或 {_yaml_freq(parent_name)}，"
            f"使二者之比落在合法分频比与容差内"
        )
        fixes.append(f"或增大 settings.period_tolerance（当前 {period_tolerance}）")

    ideal = parent_hz / child_hz if child_hz > 0 else 0
    if ideal >= 1:
        detail_lines.append(
            f"理想整数比约为 {ideal:.4g}（{parent_name} ÷ {child_name}），"
            f"但受分频比范围与容差约束。"
        )

    return DebugIssue(
        headline=f"div {div_name} 分频无法满足：{parent_name} → {child_name}",
        detail="\n".join(detail_lines),
        fixes=tuple(fixes),
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
                            fixes=(
                                f"把 {_yaml_freq(clk_name)} 改为 {arm_hz}",
                                f"或把 {_yaml_mux_sel(mux_name)} 改到能分出"
                                f" {clk_hz} Hz 的分支",
                                f"或在 mux 与 {clk_name} 之间加 div",
                            ),
                        )
                    )

    for mux_name, mux in tree.nodes.items():
        if not isinstance(mux, MuxNode) or mux.sel is not None:
            continue
        downstream_clks: List[tuple[str, int]] = []
        for clk_name, clk in tree.nodes.items():
            if not isinstance(clk, ClkNode) or clk.freq is None:
                continue
            if mux_name in _walk_upstream_chain(tree, clk_name):
                downstream_clks.append((clk_name, clk.freq))
        if not downstream_clks:
            continue
        branch_hz: List[str] = []
        for key, arm_ref in sorted(mux.source.items(), key=lambda kv: int(kv[0])):
            arm_name, _ = parse_source_endpoint(
                arm_ref, ctx=f"mux {mux_name!r}"
            )
            hz = _fixed_hz(tree.nodes[arm_name])
            if hz is None:
                sub = _walk_upstream_chain(tree, arm_name)
                for n in sub:
                    hz = _fixed_hz(tree.nodes[n])
                    if hz is not None:
                        break
            label = _hz_mhz(hz) if hz is not None else "频率未固定"
            branch_hz.append(f"sel={key} → {arm_name}（{label}）")
        clk_desc = "、".join(
            f"{n}={_hz_mhz(h)}" for n, h in downstream_clks
        )
        issues.append(
            DebugIssue(
                headline=f"mux {mux_name} 未固定 sel，与下游 clk 频率可能冲突",
                detail=(
                    f"下游固定频率：{clk_desc}。\n"
                    f"各分支前级：{'；'.join(branch_hz)}。\n"
                    f"sel 未写死时，求解器要在分支间同时满足下游目标。"
                ),
                fixes=(
                    f"为 {_yaml_mux_sel(mux_name)} 指定能达成目标频率的分支",
                    "或放宽/删除下游 clk 的 freq",
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
        fix_lines = "\n".join(f"    · {fix}" for fix in issue.fixes)
        blocks.append(
            f"[{index}] {issue.headline}\n"
            f"  {issue.detail.replace(chr(10), chr(10) + '  ')}\n"
            f"  可尝试：\n{fix_lines}"
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
        return "- 未在 YAML 中固定频率、分频比或 mux sel"
    return "\n".join(lines)
