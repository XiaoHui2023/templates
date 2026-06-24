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
from tools import run_consolver_solve

_SMT_SAFE = re.compile(r"[^a-zA-Z0-9_]")


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


def _div_needs_ratio_var(node: DivNode) -> bool:
    return node.div_kind in ("div", "div_n", "dto", "dto_n")


def build_smt2(
    tree: Tree,
    *,
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
) -> str:
    """把时钟树频率与路由约束编码为 SMT-LIB。"""
    lines: List[str] = [
        "(set-logic QF_LIA)",
    ]
    node_names = sorted(tree.nodes.keys())

    for name in node_names:
        lines.append(f"(declare-const {_sym(name, 'active')} Bool)")
        lines.append(f"(declare-const {_sym(name, 'freq')} Int)")
        node = tree.nodes[name]
        if isinstance(node, MuxNode):
            keys = sorted(node.source.keys(), key=lambda k: int(k))
            max_sel = max(int(k) for k in keys)
            lines.append(f"(declare-const {_sym(name, 'sel')} Int)")
            lines.append(f"(assert (>= {_sym(name, 'sel')} 0))")
            lines.append(f"(assert (<= {_sym(name, 'sel')} {max_sel}))")
        if isinstance(node, DivNode) and _div_needs_ratio_var(node):
            lines.append(f"(declare-const {_sym(name, 'ratio')} Int)")
        if isinstance(node, GateNode):
            lines.append(f"(declare-const {_sym(name, 'gate_open')} Bool)")

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
        parent_name, _ = parse_source_endpoint(
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
        elif node.kind in ("gate", "inv", "cell", "clk"):
            lines.append(f"(assert (=> {act_c} (= {freq_c} {freq_p})))")
        elif isinstance(node, DivNode) and node.div_kind == "cpu_gate":
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
        if node.div_kind in ("div", "div_n"):
            ratio = _sym(name, "ratio")
            lines.append(f"(assert (>= {ratio} 1))")
            lines.append(f"(assert (<= {ratio} 64))")
            lines.append(
                f"(assert (=> {act_d} (= {freq_in} (* {freq_d} {ratio}))))"
            )
        elif node.div_kind in ("dto", "dto_n"):
            ratio = _sym(name, "ratio")
            lines.append(f"(assert (>= {ratio} 2))")
            lines.append(f"(assert (<= {ratio} {DTO_MAX_RATIO}))")
            lines.append(
                f"(assert (=> {act_d} (= {freq_in} (* {freq_d} {ratio}))))"
            )
        elif node.div_kind == "div_r":
            ratio = node.ratio
            assert ratio is not None
            lines.append(
                f"(assert (=> {act_d} (= {freq_in} (* {freq_d} {ratio}))))"
            )
        elif node.div_kind == "cpu_gate":
            lines.append(f"(assert (=> {act_d} (= {freq_d} {freq_in})))")

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
            mux_sel[name] = _model_int(model, _sym(name, "sel"))
        if isinstance(node, DivNode):
            if _div_needs_ratio_var(node):
                ratios[name] = _model_int(model, _sym(name, "ratio"))
            elif node.div_kind == "div_r" and node.ratio is not None:
                ratios[name] = node.ratio
        if isinstance(node, GateNode):
            gate_open[name] = _model_bool(model, _sym(name, "gate_open"))

    return active, freq, ratios, mux_sel, gate_open


def solve_tree_constraints(
    tree: Tree,
    *,
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    timeout_ms: int | None = None,
) -> Tuple[Dict[str, bool], Dict[str, int], Dict[str, int], Dict[str, int], Dict[str, bool]]:
    """生成 SMT、调用 consolver 并解析模型。"""
    smt2 = build_smt2(
        tree,
        pll_sc_fbdiv_min=pll_sc_fbdiv_min,
        pll_sc_fbdiv_max=pll_sc_fbdiv_max,
    )
    model = run_consolver_solve(smt2, timeout_ms=timeout_ms)
    return parse_solve_model(tree, model)
