from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from formulas import (
    dw_pll_cfg,
    inno_pll_cfg,
    sc_pll_cfg,
    tci_divisors,
)
from nodes import (
    GateNode,
    PllNode,
    Tree,
    parse_source_endpoint,
)
from smt import solve_tree_constraints


@dataclass(frozen=True)
class ResolvedNode:
    name: str
    kind: str
    active: bool
    resolved_freq: int
    ratio: int
    mux_sel: int
    gate_open: bool
    pll_cfg: Dict[str, int]


@dataclass(frozen=True)
class TreeResolve:
    by_name: Dict[str, ResolvedNode]
    clk_names: Tuple[str, ...]


def _compute_pll_cfg(
    node: PllNode,
    ref_hz: int,
    *,
    fbdiv_min: int,
    fbdiv_max: int,
) -> Dict[str, int]:
    out_hz = node.freq
    if node.pll_kind == "tci":
        return tci_divisors(out_hz, ref_hz)
    if node.pll_kind == "sc":
        return sc_pll_cfg(
            out_hz, ref_hz, fbdiv_min=fbdiv_min, fbdiv_max=fbdiv_max
        )
    if node.pll_kind == "dw":
        return dw_pll_cfg(out_hz, ref_hz)
    if node.pll_kind == "inno":
        return inno_pll_cfg(
            out_hz, ref_hz, output_groups=node.output_groups
        )
    raise ValueError(f"未知 pll_kind {node.pll_kind!r}")


def resolve_tree(
    tree: Tree,
    *,
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    consolver_timeout_ms: int | None = None,
) -> TreeResolve:
    clk_nodes = [n for n in tree.nodes_ordered if n.kind == "clk"]
    if not clk_nodes:
        raise ValueError("tree 须至少含一个 kind 为 clk 的节点")

    active_map, freq_map, ratios, mux_sel, gate_open = solve_tree_constraints(
        tree,
        pll_sc_fbdiv_min=pll_sc_fbdiv_min,
        pll_sc_fbdiv_max=pll_sc_fbdiv_max,
        timeout_ms=consolver_timeout_ms,
    )

    resolved: Dict[str, ResolvedNode] = {}
    for node_name, node in tree.nodes.items():
        on_path = active_map.get(node_name, False)
        ratio = ratios.get(node_name, 0)
        sel = mux_sel.get(node_name, 0)
        gate_is_open = gate_open.get(node_name, False)
        if isinstance(node, GateNode):
            gate_is_open = on_path and gate_is_open
        pll_cfg: Dict[str, int] = {}

        if isinstance(node, PllNode) and on_path:
            parent_name, _ = parse_source_endpoint(
                node.source, ctx="pll"
            )
            ref_hz = freq_map.get(parent_name, 0)
            if ref_hz <= 0:
                raise ValueError(
                    f"pll 节点 {node_name!r} 参考频率无效"
                )
            pll_cfg = _compute_pll_cfg(
                node,
                ref_hz,
                fbdiv_min=pll_sc_fbdiv_min,
                fbdiv_max=pll_sc_fbdiv_max,
            )

        resolved_freq = freq_map.get(node_name, 0)
        is_active = on_path and (
            resolved_freq > 0 if node.kind != "pll" else node.freq > 0
        )

        resolved[node_name] = ResolvedNode(
            name=node_name,
            kind=node.kind,
            active=is_active,
            resolved_freq=resolved_freq,
            ratio=ratio,
            mux_sel=sel,
            gate_open=gate_is_open,
            pll_cfg=pll_cfg,
        )

    return TreeResolve(
        by_name=resolved,
        clk_names=tuple(n.name for n in clk_nodes),
    )
