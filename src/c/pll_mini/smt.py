from __future__ import annotations

import re
from typing import Dict, List, Mapping, Tuple

from formulas import DTO_MAX_RATIO
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
from tools import run_consolver_solve

_SMT_SAFE = re.compile(r"[^a-zA-Z0-9_]")
_FREQ_TOL_DEN = 100


def _sym(node_name: str, suffix: str) -> str:
    base = _SMT_SAFE.sub("_", node_name)
    if base and base[0].isdigit():
        base = f"n_{base}"
    return f"{suffix}_{base}"


def _ite_chain(pairs: List[Tuple[str, str]], default: str) -> str:
    if not pairs:
        return default
    expr = default
    for cond, val in reversed(pairs):
        expr = f"(ite {cond} {val} {expr})"
    return expr


def _freq_tolerance_bounds(period_tolerance: float) -> tuple[int, int, int]:
    tol_num = round(period_tolerance * _FREQ_TOL_DEN)
    return _FREQ_TOL_DEN - tol_num, _FREQ_TOL_DEN + tol_num, _FREQ_TOL_DEN


def _div_needs_ratio_var(node: DivNode) -> bool:
    return node.div_kind in ("div", "div_n", "dto", "dto_n", "cpu_gate")


def _append_div_freq_constraint(
    lines: List[str],
    *,
    active: str,
    freq_in: str,
    freq_out: str,
    ratio: str,
    freq_hw: str,
    rem: str,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> None:
    lines.append(f"(assert (=> {active} (> {freq_hw} 0)))")
    lines.append(f"(assert (=> {active} (>= {rem} 0)))")
    lines.append(f"(assert (=> {active} (< {rem} {ratio})))")
    lines.append(
        f"(assert (=> {active} (= {freq_in} (+ (* {freq_hw} {ratio}) {rem}))))"
    )
    lines.append(
        f"(assert (=> {active} (<= (* {freq_out} {tol_lo}) (* {freq_hw} {tol_den}))))"
    )
    lines.append(
        f"(assert (=> {active} (>= (* {freq_out} {tol_hi}) (* {freq_hw} {tol_den}))))"
    )


def build_smt2(
    tree: Tree,
    *,
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    period_tolerance: float,
) -> str:
    """把时钟树频率与路由约束编码为 SMT-LIB。"""
    lines: List[str] = [
        "(set-logic QF_LIA)",
    ]
    node_names = sorted(tree.nodes.keys())
    tol_lo, tol_hi, tol_den = _freq_tolerance_bounds(period_tolerance)

    for name in node_names:
        lines.append(f"(declare-const {_sym(name, 'active')} Bool)")
        lines.append(f"(declare-const {_sym(name, 'freq')} Int)")
        node = tree.nodes[name]
        if isinstance(node, MuxNode):
            keys = sorted(node.source.keys(), key=lambda k: int(k))
            max_sel = max(int(k) for k in keys)
            lines.append(f"(declare-const {_sym(name, 'sel')} Int)")
            if node.sel is not None:
                lines.append(f"(assert (= {_sym(name, 'sel')} {node.sel}))")
            else:
                lines.append(f"(assert (>= {_sym(name, 'sel')} 0))")
                lines.append(f"(assert (<= {_sym(name, 'sel')} {max_sel}))")
        if isinstance(node, DivNode) and _div_needs_ratio_var(node):
            lines.append(f"(declare-const {_sym(name, 'ratio')} Int)")
            if node.ratio is not None:
                lines.append(f"(assert (= {_sym(name, 'ratio')} {node.ratio}))")
        if isinstance(node, DivNode):
            lines.append(f"(declare-const {_sym(name, 'freq_hw')} Int)")
            lines.append(f"(declare-const {_sym(name, 'rem')} Int)")
        if isinstance(node, GateNode):
            lines.append(f"(declare-const {_sym(name, 'gate_open')} Bool)")
            if node.open is not None:
                lit = "true" if node.open else "false"
                lines.append(
                    f"(assert (= {_sym(name, 'gate_open')} {lit}))"
                )

    for name in node_names:
        node = tree.nodes[name]
        if node.kind == "source":
            if node.freq > 0:
                lines.append(f"(assert {_sym(name, 'active')})")
                lines.append(
                    f"(assert (= {_sym(name, 'freq')} {node.freq}))"
                )
        elif isinstance(node, ClkNode):
            lines.append(f"(assert {_sym(name, 'active')})")
            if node.freq is not None:
                lines.append(
                    f"(assert (= {_sym(name, 'freq')} {node.freq}))"
                )
        elif isinstance(node, PllNode):
            lines.append(
                f"(assert (=> {_sym(name, 'active')} "
                f"(= {_sym(name, 'freq')} {node.freq})))"
            )

    for name in node_names:
        node = tree.nodes[name]
        if node.kind in ("source", "mux"):
            continue
        parent_name, out_group = parse_source_endpoint(
            node.source, ctx=f"节点 {name!r} source"
        )
        parent = tree.nodes[parent_name]
        act_c = _sym(name, "active")
        act_p = _sym(parent_name, "active")
        freq_c = _sym(name, "freq")
        freq_p = _sym(parent_name, "freq")
        lines.append(f"(assert (=> {act_c} {act_p}))")
        if parent.kind == "mux":
            lines.append(f"(assert (=> {act_c} (= {freq_c} {freq_p})))")
        elif isinstance(parent, DivNode) and parent.div_kind == "cpu_gate":
            if out_group == CPU_GATE_PASS_THROUGH_GROUP:
                pass_parent_name, _ = parse_source_endpoint(
                    parent.source, ctx=f"cpu_gate {parent_name!r} source"
                )
                freq_pass = _sym(pass_parent_name, "freq")
                lines.append(
                    f"(assert (=> {act_c} (= {freq_c} {freq_pass})))"
                )
            else:
                lines.append(f"(assert (=> {act_c} (= {freq_c} {freq_p})))")
        elif node.kind in ("gate", "inv", "cell", "clk"):
            lines.append(f"(assert (=> {act_c} (= {freq_c} {freq_p})))")
        elif node.kind == "pll":
            pass
        elif isinstance(node, DivNode):
            pass

    for name in node_names:
        node = tree.nodes[name]
        if not isinstance(node, MuxNode):
            continue
        act_m = _sym(name, "active")
        freq_m = _sym(name, "freq")
        sel_m = _sym(name, "sel")
        keys = sorted(node.source.keys(), key=lambda k: int(k))
        peer_names: List[str] = []
        freq_arms: List[Tuple[str, str]] = []
        active_arms: List[str] = []
        for key in keys:
            peer_ref = node.source[key]
            peer_name, _ = parse_source_endpoint(
                peer_ref, ctx=f"mux {name!r}"
            )
            peer_names.append(peer_name)
            cond = f"(= {sel_m} {key})"
            freq_arms.append((cond, _sym(peer_name, "freq")))
            active_arms.append(
                f"(and {cond} {_sym(peer_name, 'active')})"
            )
        default_peer = peer_names[0]
        lines.append(
            f"(assert (=> {act_m} (= {freq_m} "
            f"{_ite_chain(freq_arms, _sym(default_peer, 'freq'))})))"
        )
        lines.append(
            f"(assert (=> {act_m} (or {' '.join(active_arms)})))"
        )

    for name in node_names:
        node = tree.nodes[name]
        if not isinstance(node, DivNode):
            continue
        parent_name, _ = parse_source_endpoint(
            node.source, ctx="div"
        )
        act_d = _sym(name, "active")
        freq_d = _sym(name, "freq")
        freq_in = _sym(parent_name, "freq")
        freq_hw = _sym(name, "freq_hw")
        rem = _sym(name, "rem")
        if node.div_kind in ("div", "div_n"):
            ratio = _sym(name, "ratio")
            lines.append(f"(assert (>= {ratio} 1))")
            lines.append(f"(assert (<= {ratio} 64))")
            _append_div_freq_constraint(
                lines,
                active=act_d,
                freq_in=freq_in,
                freq_out=freq_d,
                ratio=ratio,
                freq_hw=freq_hw,
                rem=rem,
                tol_lo=tol_lo,
                tol_hi=tol_hi,
                tol_den=tol_den,
            )
        elif node.div_kind in ("dto", "dto_n"):
            ratio = _sym(name, "ratio")
            lines.append(f"(assert (>= {ratio} 2))")
            lines.append(f"(assert (<= {ratio} {DTO_MAX_RATIO}))")
            _append_div_freq_constraint(
                lines,
                active=act_d,
                freq_in=freq_in,
                freq_out=freq_d,
                ratio=ratio,
                freq_hw=freq_hw,
                rem=rem,
                tol_lo=tol_lo,
                tol_hi=tol_hi,
                tol_den=tol_den,
            )
        elif node.div_kind == "div_r":
            ratio = node.ratio
            assert ratio is not None
            _append_div_freq_constraint(
                lines,
                active=act_d,
                freq_in=freq_in,
                freq_out=freq_d,
                ratio=str(ratio),
                freq_hw=freq_hw,
                rem=rem,
                tol_lo=tol_lo,
                tol_hi=tol_hi,
                tol_den=tol_den,
            )
        elif node.div_kind == "cpu_gate":
            ratio = _sym(name, "ratio")
            ratio_allowed = " ".join(
                f"(= {ratio} {value})" for value in (2, 3, 4, 6)
            )
            lines.append(f"(assert (or {ratio_allowed}))")
            _append_div_freq_constraint(
                lines,
                active=act_d,
                freq_in=freq_in,
                freq_out=freq_d,
                ratio=ratio,
                freq_hw=freq_hw,
                rem=rem,
                tol_lo=tol_lo,
                tol_hi=tol_hi,
                tol_den=tol_den,
            )

    for name in node_names:
        node = tree.nodes[name]
        if isinstance(node, GateNode):
            act_g = _sym(name, "active")
            open_g = _sym(name, "gate_open")
            lines.append(f"(assert (=> {act_g} {open_g}))")

    for name in node_names:
        act = _sym(name, "active")
        freq = _sym(name, "freq")
        lines.append(f"(assert (=> {act} (> {freq} 0)))")
        lines.append(f"(assert (=> (not {act}) (= {freq} 0)))")

    _ = pll_sc_fbdiv_min
    _ = pll_sc_fbdiv_max

    lines.append("(check-sat)")
    lines.append("(get-model)")
    return "\n".join(lines) + "\n"


def _model_bool(model: Mapping[str, object], sym: str) -> bool:
    val = model.get(sym)
    if val is True:
        return True
    if val is False:
        return False
    if isinstance(val, int):
        return val != 0
    raise ValueError(f"模型变量 {sym!r} 不是布尔值: {val!r}")


def _model_int(model: Mapping[str, object], sym: str) -> int:
    val = model.get(sym)
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, int):
        return val
    if isinstance(val, dict) and "value" in val:
        inner = val["value"]
        if isinstance(inner, int):
            return inner
    raise ValueError(f"模型变量 {sym!r} 不是整数: {val!r}")


def parse_solve_model(
    tree: Tree,
    model: Mapping[str, object],
) -> Tuple[
    Dict[str, bool],
    Dict[str, int],
    Dict[str, int],
    Dict[str, int],
    Dict[str, bool],
]:
    """从 consolver 模型解析 active、freq、ratio、mux_sel、gate_open。"""
    active: Dict[str, bool] = {}
    freq: Dict[str, int] = {}
    ratios: Dict[str, int] = {}
    mux_sel: Dict[str, int] = {}
    gate_open: Dict[str, bool] = {}

    for name, node in tree.nodes.items():
        active[name] = _model_bool(model, _sym(name, "active"))
        freq[name] = _model_int(model, _sym(name, "freq"))
        if isinstance(node, MuxNode):
            mux_sel[name] = (
                node.sel
                if node.sel is not None
                else _model_int(model, _sym(name, "sel"))
            )
        if isinstance(node, DivNode):
            if _div_needs_ratio_var(node):
                ratios[name] = (
                    node.ratio
                    if node.ratio is not None
                    else _model_int(model, _sym(name, "ratio"))
                )
            elif node.div_kind == "div_r" and node.ratio is not None:
                ratios[name] = node.ratio
        if isinstance(node, GateNode):
            gate_open[name] = (
                node.open != 0
                if node.open is not None
                else _model_bool(model, _sym(name, "gate_open"))
            )

    return active, freq, ratios, mux_sel, gate_open


def solve_tree_constraints(
    tree: Tree,
    *,
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    period_tolerance: float,
    timeout_ms: int | None = None,
) -> Tuple[Dict[str, bool], Dict[str, int], Dict[str, int], Dict[str, int], Dict[str, bool]]:
    """生成 SMT、调用 consolver 并解析模型。"""
    smt2 = build_smt2(
        tree,
        pll_sc_fbdiv_min=pll_sc_fbdiv_min,
        pll_sc_fbdiv_max=pll_sc_fbdiv_max,
        period_tolerance=period_tolerance,
    )
    model = run_consolver_solve(smt2, timeout_ms=timeout_ms)
    return parse_solve_model(tree, model)
