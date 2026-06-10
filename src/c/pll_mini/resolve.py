from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from formulas import (
    div_ratio_from_freq,
    dto_ratio_from_freq,
    dw_pll_cfg,
    inno_pll_cfg,
    sc_pll_cfg,
    tci_divisors,
)
from nodes import (
    DivNode,
    DtoNode,
    GateNode,
    MuxNode,
    PllNode,
    Tree,
    parse_source_endpoint,
)


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


def _subtree_names(root_name: str, tree: Tree) -> set[str]:
    names = {root_name}
    stack = [root_name]
    while stack:
        current = stack.pop()
        for child in tree.children_by_node.get(current, []):
            if child not in names:
                names.add(child)
                stack.append(child)
    return names


def _can_reach_clk(peer_ref: str, clk_name: str, tree: Tree) -> bool:
    device, _out_idx = parse_source_endpoint(peer_ref, ctx="mux")
    return clk_name in _subtree_names(device, tree)


def _resolve_mux_sel(mux: MuxNode, clk_name: str, tree: Tree) -> int:
    for key in sorted(mux.source.keys(), key=lambda k: int(k)):
        if _can_reach_clk(mux.source[key], clk_name, tree):
            return int(key)
    raise ValueError(
        f"mux 节点 {mux.name!r} 无输入能到达 clk {clk_name!r}"
    )


def _trace_active_path(
    tree: Tree, clk_name: str
) -> tuple[set[str], Dict[str, int]]:
    active: set[str] = set()
    mux_sel: Dict[str, int] = {}

    def visit(node_name: str) -> None:
        if node_name in active:
            return
        active.add(node_name)
        node = tree.nodes[node_name]
        if node.kind == "source":
            return
        if node.kind == "mux":
            return
        parent_name, _out_idx = parse_source_endpoint(
            node.source, ctx=f"节点 {node_name!r} source"
        )
        parent = tree.nodes[parent_name]
        if parent.kind == "mux":
            sel = _resolve_mux_sel(parent, clk_name, tree)
            mux_sel[parent.name] = sel
            peer = parent.source[str(sel)]
            peer_name, _ = parse_source_endpoint(
                peer, ctx=f"mux {parent.name!r}"
            )
            visit(parent.name)
            visit(peer_name)
        else:
            visit(parent_name)

    visit(clk_name)
    return active, mux_sel


def _active_children(node_name: str, tree: Tree, active: set[str]) -> List[str]:
    return sorted(
        c for c in tree.children_by_node.get(node_name, []) if c in active
    )


def _required_out_freq(
    node_name: str,
    tree: Tree,
    active: set[str],
    cache: Dict[str, int],
) -> int:
    if node_name in cache:
        return cache[node_name]
    node = tree.nodes[node_name]
    if node.kind == "clk":
        cache[node_name] = node.freq
        return node.freq
    children = _active_children(node_name, tree, active)
    if len(children) != 1:
        raise ValueError(
            f"活动路径上节点 {node_name!r} 须有且仅有一个活动下游，得到 {children}"
        )
    cache[node_name] = _required_out_freq(
        children[0], tree, active, cache
    )
    return cache[node_name]


def _topo_active_order(
    tree: Tree,
    active: set[str],
    mux_sel: Dict[str, int],
) -> List[str]:
    order: List[str] = []
    seen: set[str] = set()

    def visit_upstream(node_name: str) -> None:
        if node_name in seen or node_name not in active:
            return
        node = tree.nodes[node_name]
        if node.kind == "source":
            seen.add(node_name)
            order.append(node_name)
            return
        if node.kind == "mux":
            sel = mux_sel[node_name]
            peer = node.source[str(sel)]
            peer_name, _ = parse_source_endpoint(peer, ctx="mux")
            visit_upstream(peer_name)
            seen.add(node_name)
            order.append(node_name)
            return
        parent_name, _ = parse_source_endpoint(
            node.source, ctx=f"节点 {node_name!r}"
        )
        parent = tree.nodes[parent_name]
        if parent.kind == "mux":
            sel = mux_sel[parent_name]
            peer = parent.source[str(sel)]
            peer_name, _ = parse_source_endpoint(peer, ctx="mux")
            visit_upstream(peer_name)
            visit_upstream(parent_name)
        else:
            visit_upstream(parent_name)
        seen.add(node_name)
        order.append(node_name)

    for node_name in sorted(active):
        visit_upstream(node_name)
    deduped: List[str] = []
    for node_name in order:
        if node_name not in deduped:
            deduped.append(node_name)
    return deduped


def _compute_ratios(
    tree: Tree,
    active: set[str],
    mux_sel: Dict[str, int],
) -> Dict[str, int]:
    req_cache: Dict[str, int] = {}
    out_hz_map: Dict[str, int] = {}
    ratios: Dict[str, int] = {}
    for node_name in _topo_active_order(tree, active, mux_sel):
        node = tree.nodes[node_name]
        if node.kind in ("source", "pll"):
            out_hz_map[node_name] = node.freq
            continue
        if node.kind == "mux":
            sel = mux_sel[node_name]
            peer = node.source[str(sel)]
            peer_name, _ = parse_source_endpoint(peer, ctx="mux")
            out_hz_map[node_name] = out_hz_map[peer_name]
            continue
        if node.kind in ("gate", "inv"):
            parent_name, _ = parse_source_endpoint(
                node.source, ctx=node.kind
            )
            out_hz_map[node_name] = out_hz_map[parent_name]
            continue
        if isinstance(node, DivNode):
            parent_name, _ = parse_source_endpoint(
                node.source, ctx="div"
            )
            in_hz = out_hz_map[parent_name]
            target_out = _required_out_freq(
                node_name, tree, active, req_cache
            )
            ratio = div_ratio_from_freq(in_hz, target_out)
            ratios[node_name] = ratio
            out_hz_map[node_name] = in_hz // ratio
            continue
        if isinstance(node, DtoNode):
            parent_name, _ = parse_source_endpoint(
                node.source, ctx="dto"
            )
            in_hz = out_hz_map[parent_name]
            target_out = _required_out_freq(
                node_name, tree, active, req_cache
            )
            ratio = dto_ratio_from_freq(in_hz, target_out)
            ratios[node_name] = ratio
            out_hz_map[node_name] = in_hz // ratio
    return ratios


def _forward_freq(
    node_name: str,
    tree: Tree,
    active: set[str],
    mux_sel: Dict[str, int],
    ratios: Dict[str, int],
    cache: Dict[str, int],
) -> int:
    if node_name in cache:
        return cache[node_name]
    node = tree.nodes[node_name]
    if node_name not in active:
        cache[node_name] = 0
        return 0
    if node.kind == "source":
        cache[node_name] = node.freq
        return node.freq
    if node.kind == "pll":
        cache[node_name] = node.freq
        return node.freq
    if node.kind == "mux":
        sel = mux_sel[node_name]
        peer = node.source[str(sel)]
        peer_name, _ = parse_source_endpoint(peer, ctx="mux")
        cache[node_name] = _forward_freq(
            peer_name, tree, active, mux_sel, ratios, cache
        )
        return cache[node_name]
    parent_name, _ = parse_source_endpoint(
        node.source, ctx=f"节点 {node_name!r}"
    )
    in_hz = _forward_freq(
        parent_name, tree, active, mux_sel, ratios, cache
    )
    if node.kind in ("gate", "inv"):
        cache[node_name] = in_hz
        return in_hz
    if node.kind == "div":
        ratio = ratios[node_name]
        out_hz = in_hz // ratio
        cache[node_name] = out_hz
        return out_hz
    if node.kind == "dto":
        ratio = ratios[node_name]
        out_hz = in_hz // ratio
        cache[node_name] = out_hz
        return out_hz
    if node.kind == "clk":
        cache[node_name] = node.freq
        return node.freq
    raise ValueError(f"未知 kind {node.kind!r}")


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
            out_hz, ref_hz, output_count=node.output_count
        )
    raise ValueError(f"未知 pll_kind {node.pll_kind!r}")


def resolve_tree(
    tree: Tree,
    *,
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
) -> TreeResolve:
    clk_nodes = [n for n in tree.nodes_ordered if n.kind == "clk"]
    if len(clk_nodes) != 1:
        raise ValueError("tree 须恰好含一个 kind 为 clk 的节点")

    clk = clk_nodes[0]
    active, mux_sel = _trace_active_path(tree, clk.name)

    ratios = _compute_ratios(tree, active, mux_sel)

    freq_cache: Dict[str, int] = {}
    resolved: Dict[str, ResolvedNode] = {}

    for node_name, node in tree.nodes.items():
        on_path = node_name in active
        ratio = ratios.get(node_name, 0)
        sel = mux_sel.get(node_name, 0)
        gate_open = isinstance(node, GateNode) and on_path
        pll_cfg: Dict[str, int] = {}

        if isinstance(node, PllNode) and on_path:
            parent_name, _ = parse_source_endpoint(
                node.source, ctx="pll"
            )
            ref_hz = _forward_freq(
                parent_name,
                tree,
                active,
                mux_sel,
                ratios,
                freq_cache,
            )
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

        resolved_freq = _forward_freq(
            node_name, tree, active, mux_sel, ratios, freq_cache
        )
        is_active = on_path and (
            resolved_freq > 0
            if node.kind != "pll"
            else node.freq > 0
        )

        resolved[node_name] = ResolvedNode(
            name=node_name,
            kind=node.kind,
            active=is_active,
            resolved_freq=resolved_freq,
            ratio=ratio,
            mux_sel=sel,
            gate_open=gate_open,
            pll_cfg=pll_cfg,
        )

    return TreeResolve(
        by_name=resolved,
        clk_names=(clk.name,),
    )
