from __future__ import annotations

import time
from typing import Dict, Iterator, List, Set, Tuple

from formulas import (
    CPU_GATE_RATIOS,
    DTO_MAX_RATIO,
    div_hw_from_input,
    dto_ratio_candidates_for_pair,
    find_div_ratio,
    freq_tolerance_bounds,
)
from freq_model import (
    Port,
    backward_required_nodes,
    collect_freq_targets,
    is_cpu_gate_passthrough_group,
    is_mux_exclusive_peer,
    is_passthrough_kind,
    output_ports,
    parent_port_for_child,
    parse_port_ref,
)
from nodes import (
    ClkNode,
    DivNode,
    GateNode,
    MuxNode,
    PllNode,
    Tree,
    parse_source_endpoint,
)
from pll_search import search_pll_coefficients
from solve_model import SolveModel
from tools import log_stage_done, log_stage_start


def search_tree_constraints(
    tree: Tree,
    *,
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    period_tolerance: float,
    timeout_ms: int | None = None,
) -> SolveModel:
    targets = collect_freq_targets(tree)
    if not targets:
        raise ValueError("须至少有一个带正频率的 clk 节点")

    tol_lo, tol_hi, tol_den = freq_tolerance_bounds(period_tolerance)
    deadline = (
        time.perf_counter() + timeout_ms / 1000.0
        if timeout_ms is not None
        else None
    )

    started_at = log_stage_start(
        "search",
        "solve",
        "tree constraints",
        nodes=len(tree.nodes),
        targets=len(targets),
    )
    try:
        model = _search_tree(
            tree,
            targets=targets,
            pll_sc_fbdiv_min=pll_sc_fbdiv_min,
            pll_sc_fbdiv_max=pll_sc_fbdiv_max,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
            deadline=deadline,
        )
    except RuntimeError:
        log_stage_done(
            "search",
            "solve",
            "tree constraints",
            started_at,
            failed=True,
        )
        raise
    log_stage_done(
        "search",
        "solve",
        "tree constraints",
        started_at,
        model_items=len(model.port_freq),
    )
    return model


def _search_tree(
    tree: Tree,
    *,
    targets: List[Tuple[str, int]],
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
    deadline: float | None,
) -> SolveModel:
    required = backward_required_nodes(tree, targets)
    free_muxes = _free_mux_nodes(tree, required)
    free_divs = _ordered_free_div_nodes(tree, required, targets)

    mux_sel: Dict[str, int] = {}
    for name in required:
        node = tree.nodes[name]
        if isinstance(node, MuxNode) and node.sel is not None:
            mux_sel[name] = node.sel

    ratios: Dict[str, int] = {}
    for name in required:
        node = tree.nodes[name]
        if isinstance(node, DivNode) and node.ratio is not None:
            ratios[name] = node.ratio

    for assignment in _iter_mux_assignments(tree, free_muxes):
        if deadline is not None and time.perf_counter() > deadline:
            raise RuntimeError("时钟树约束求解超时或无法判定")
        trial_mux = {**mux_sel, **assignment}
        if not _mux_assignments_compatible(tree, targets, trial_mux):
            continue
        active = _compute_active(tree, targets, trial_mux)
        if not _active_covers_targets(tree, targets, active, trial_mux):
            continue
        trial_ratios = dict(ratios)
        if not _assign_div_ratios(
            tree,
            free_divs,
            targets,
            active,
            trial_mux,
            trial_ratios,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        ):
            continue
        port_freq = _propagate_port_freqs(
            tree,
            active=active,
            mux_sel=trial_mux,
            ratios=trial_ratios,
            targets=targets,
        )
        if port_freq is None:
            continue
        if not _clk_targets_match(targets, port_freq):
            continue
        pll_vars = _compute_pll_vars(
            tree,
            active=active,
            port_freq=port_freq,
            pll_sc_fbdiv_min=pll_sc_fbdiv_min,
            pll_sc_fbdiv_max=pll_sc_fbdiv_max,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        )
        if pll_vars is None:
            continue
        model = _assemble_model(
            tree,
            active=active,
            port_freq=port_freq,
            mux_sel=trial_mux,
            ratios=trial_ratios,
            pll_vars=pll_vars,
        )
        return model

    raise RuntimeError("时钟树约束互相矛盾，无解")


def _free_mux_nodes(tree: Tree, required: Set[str]) -> List[str]:
    out: List[str] = []
    for name in sorted(required):
        node = tree.nodes[name]
        if isinstance(node, MuxNode) and node.sel is None:
            out.append(name)
    return out


def _ordered_free_div_nodes(
    tree: Tree,
    required: Set[str],
    targets: List[Tuple[str, int]],
) -> List[str]:
    free: List[str] = []
    for name in sorted(required):
        node = tree.nodes[name]
        if not isinstance(node, DivNode):
            continue
        if node.ratio is not None or node.div_kind == "div_r":
            continue
        if node.div_kind in ("div", "div_n", "dto", "dto_n", "cpu_gate"):
            free.append(name)

    def depth(name: str) -> int:
        best = 0
        for clk_name, _ in targets:
            path = _find_downstream_path(tree, name, clk_name)
            if path is not None:
                best = max(best, len(path))
        return best

    return sorted(free, key=depth, reverse=True)


def _iter_mux_assignments(
    tree: Tree,
    free_muxes: List[str],
) -> Iterator[Dict[str, int]]:
    if not free_muxes:
        yield {}
        return

    mux_name = free_muxes[0]
    rest = free_muxes[1:]
    node = tree.nodes[mux_name]
    assert isinstance(node, MuxNode)
    keys = sorted(node.source.keys(), key=lambda k: int(k))
    for key in keys:
        for tail in _iter_mux_assignments(tree, rest):
            yield {mux_name: int(key), **tail}


def _mux_assignments_compatible(
    tree: Tree,
    targets: List[Tuple[str, int]],
    mux_sel: Dict[str, int],
) -> bool:
    for clk_name, _ in targets:
        if _walk_upstream(tree, clk_name, mux_sel) is None:
            return False
    return True


def _walk_upstream(
    tree: Tree,
    start: str,
    mux_sel: Dict[str, int],
) -> List[str] | None:
    chain = [start]
    name = start
    seen = {start}
    while True:
        node = tree.nodes[name]
        if isinstance(node, GateNode) and node.open == 0:
            return None
        if node.kind == "source":
            return chain
        if isinstance(node, MuxNode):
            sel = mux_sel.get(name, node.sel)
            if sel is None:
                return None
            arm = node.source.get(str(sel))
            if not arm:
                return None
            peer_name, _ = parse_source_endpoint(arm, ctx=f"mux {name!r}")
            if peer_name in seen:
                return None
            seen.add(peer_name)
            chain.append(peer_name)
            name = peer_name
            continue
        try:
            parent_port = parent_port_for_child(tree, name)
        except ValueError:
            return None
        parent_name = parent_port.node
        if parent_name in seen:
            return None
        parent = tree.nodes[parent_name]
        if isinstance(parent, MuxNode):
            seen.add(parent_name)
            chain.append(parent_name)
            sel = mux_sel.get(parent_name, parent.sel)
            if sel is None:
                return None
            arm = parent.source.get(str(sel))
            if not arm:
                return None
            peer_name, _ = parse_source_endpoint(arm, ctx=f"mux {parent_name!r}")
            if peer_name in seen:
                return None
            seen.add(peer_name)
            chain.append(peer_name)
            name = peer_name
            continue
        seen.add(parent_name)
        chain.append(parent_name)
        name = parent_name


def _compute_active(
    tree: Tree,
    targets: List[Tuple[str, int]],
    mux_sel: Dict[str, int],
) -> Set[str]:
    active: Set[str] = set()
    for clk_name, _ in targets:
        chain = _walk_upstream(tree, clk_name, mux_sel)
        if chain is None:
            continue
        for name in chain:
            active.add(name)
    for name in list(active):
        node = tree.nodes[name]
        if isinstance(node, MuxNode):
            sel = mux_sel.get(name, node.sel)
            if sel is None:
                continue
            arm = node.source.get(str(sel))
            if not arm:
                continue
            peer_name, _ = parse_source_endpoint(arm, ctx=f"mux {name!r}")
            active.add(peer_name)
            if is_mux_exclusive_peer(tree, name, peer_name):
                continue
            _mark_upstream_active(tree, peer_name, active, mux_sel)
    return active


def _mark_upstream_active(
    tree: Tree,
    start: str,
    active: Set[str],
    mux_sel: Dict[str, int],
) -> None:
    stack = [start]
    seen = set(active)
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        active.add(name)
        node = tree.nodes[name]
        if node.kind == "source":
            continue
        if isinstance(node, GateNode) and node.open == 0:
            continue
        if isinstance(node, MuxNode):
            sel = mux_sel.get(name, node.sel)
            if sel is None:
                continue
            arm = node.source.get(str(sel))
            if not arm:
                continue
            peer_name, _ = parse_source_endpoint(arm, ctx=f"mux {name!r}")
            stack.append(peer_name)
            continue
        try:
            parent_port = parent_port_for_child(tree, name)
        except ValueError:
            continue
        stack.append(parent_port.node)


def _active_covers_targets(
    tree: Tree,
    targets: List[Tuple[str, int]],
    active: Set[str],
    mux_sel: Dict[str, int],
) -> bool:
    for clk_name, _ in targets:
        if clk_name not in active:
            return False
        if _walk_upstream(tree, clk_name, mux_sel) is None:
            return False
    return True


def _assign_div_ratios(
    tree: Tree,
    free_divs: List[str],
    targets: List[Tuple[str, int]],
    active: Set[str],
    mux_sel: Dict[str, int],
    ratios: Dict[str, int],
    *,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> bool:
    for div_name in free_divs:
        if div_name not in active:
            continue
        node = tree.nodes[div_name]
        if not isinstance(node, DivNode):
            continue
        f_in = _required_parent_hz_for_div(
            tree,
            div_name,
            targets,
            active,
            mux_sel,
            ratios,
        )
        if f_in is None or f_in <= 0:
            return False
        required_outs = _required_div_outputs(
            tree,
            div_name,
            targets,
            active,
            mux_sel,
            ratios,
        )
        if not required_outs:
            return False
        if node.div_kind == "cpu_gate":
            unique = set(required_outs.values())
            if len(unique) != 1:
                return False
            want_out = next(iter(unique))
        else:
            want_out = required_outs.get("")
            if want_out is None:
                return False
            unique = set(required_outs.values())
            if len(unique) != 1:
                return False
        ratio = _pick_div_ratio(
            node,
            f_in=f_in,
            want_out_hz=want_out,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        )
        if ratio is None:
            return False
        ratios[div_name] = ratio
    return True


def _required_parent_hz_for_div(
    tree: Tree,
    div_name: str,
    targets: List[Tuple[str, int]],
    active: Set[str],
    mux_sel: Dict[str, int],
    ratios: Dict[str, int],
) -> int | None:
    parent_port = parent_port_for_child(tree, div_name)
    return _node_output_hz(
        tree,
        parent_port.node,
        parent_port.group,
        targets,
        active,
        mux_sel,
        ratios,
    )


def _node_output_hz(
    tree: Tree,
    node_name: str,
    group: str,
    targets: List[Tuple[str, int]],
    active: Set[str],
    mux_sel: Dict[str, int],
    ratios: Dict[str, int],
) -> int | None:
    if node_name not in active:
        return None
    node = tree.nodes[node_name]
    if node.kind == "source":
        return node.freq
    if isinstance(node, PllNode):
        if node.pll_kind == "inno":
            reqs = _required_inno_group_hz(
                tree, node_name, targets, active, mux_sel, ratios
            )
            return reqs.get(group)
        return node.freq
    if isinstance(node, DivNode):
        outs = _required_div_outputs(
            tree, node_name, targets, active, mux_sel, ratios
        )
        return outs.get(group, outs.get(""))
    if isinstance(node, MuxNode):
        sel = mux_sel.get(node_name, node.sel)
        if sel is None:
            return None
        arm = node.source.get(str(sel))
        if not arm:
            return None
        arm_port = parse_port_ref(arm, ctx=f"mux {node_name!r}")
        return _node_output_hz(
            tree,
            arm_port.node,
            arm_port.group,
            targets,
            active,
            mux_sel,
            ratios,
        )
    if is_passthrough_kind(node.kind):
        parent_port = parent_port_for_child(tree, node_name)
        return _node_output_hz(
            tree,
            parent_port.node,
            parent_port.group,
            targets,
            active,
            mux_sel,
            ratios,
        )
    return None


def _required_div_outputs(
    tree: Tree,
    div_name: str,
    targets: List[Tuple[str, int]],
    active: Set[str],
    mux_sel: Dict[str, int],
    ratios: Dict[str, int],
) -> Dict[str, int]:
    node = tree.nodes[div_name]
    assert isinstance(node, DivNode)
    out: Dict[str, int] = {}
    if node.div_kind == "cpu_gate":
        for port in output_ports(tree, div_name):
            if is_cpu_gate_passthrough_group(port.group):
                continue
            for clk_name, clk_hz in targets:
                if not _clk_uses_cpu_gate_port(tree, clk_name, div_name, port.group):
                    continue
                req = _inverse_required_at_div_output(
                    tree,
                    div_name,
                    clk_name,
                    clk_hz,
                    ratios,
                )
                if req is None:
                    continue
                prev = out.get(port.group)
                if prev is not None and prev != req:
                    out[port.group] = -1
                else:
                    out[port.group] = req
        if -1 in out.values():
            return {}
        return {k: v for k, v in out.items() if v > 0}

    for clk_name, clk_hz in targets:
        if div_name not in active:
            continue
        if not _reachable_downstream(tree, div_name, clk_name):
            continue
        req = _inverse_required_at_div_output(
            tree,
            div_name,
            clk_name,
            clk_hz,
            ratios,
        )
        if req is None:
            continue
        prev = out.get("")
        if prev is not None and prev != req:
            out[""] = -1
        else:
            out[""] = req
    if -1 in out.values():
        return {}
    return {k: v for k, v in out.items() if v > 0}


def _inverse_required_at_div_output(
    tree: Tree,
    div_name: str,
    clk_name: str,
    clk_hz: int,
    ratios: Dict[str, int],
) -> int | None:
    path = _find_downstream_path(tree, div_name, clk_name)
    if path is None:
        return None
    req = clk_hz
    idx = path.index(div_name)
    for downstream in reversed(path[idx + 1 :]):
        node = tree.nodes[downstream]
        if node.kind in ("gate", "inv", "cell", "clk"):
            continue
        if isinstance(node, MuxNode):
            continue
        if isinstance(node, DivNode):
            ratio = node.ratio if node.ratio is not None else ratios.get(downstream)
            if ratio is None:
                return None
            if node.div_kind == "cpu_gate" and downstream != div_name:
                clk_node = tree.nodes[clk_name]
                _, clk_group = parse_source_endpoint(
                    clk_node.source, ctx=f"clk {clk_name!r}"
                )
                if is_cpu_gate_passthrough_group(clk_group):
                    continue
                req *= ratio
            elif node.div_kind != "cpu_gate":
                req *= ratio
    return req


def _pick_div_ratio(
    node: DivNode,
    *,
    f_in: int,
    want_out_hz: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> int | None:
    if node.div_kind in ("div", "div_n"):
        candidates = tuple(range(1, 65))
    elif node.div_kind == "cpu_gate":
        candidates = tuple(sorted(CPU_GATE_RATIOS))
    elif node.div_kind in ("dto", "dto_n"):
        candidates = dto_ratio_candidates_for_pair(
            f_in,
            want_out_hz,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        )
        if not candidates:
            candidates = tuple(range(2, min(65, DTO_MAX_RATIO + 1)))
    else:
        return None
    return find_div_ratio(
        f_in,
        want_out_hz,
        candidates,
        tol_lo=tol_lo,
        tol_hi=tol_hi,
        tol_den=tol_den,
    )


def _reachable_downstream(tree: Tree, start: str, target: str) -> bool:
    return _find_downstream_path(tree, start, target) is not None


def _clk_uses_cpu_gate_port(
    tree: Tree,
    clk_name: str,
    cpu_gate_name: str,
    group: str,
) -> bool:
    clk_node = tree.nodes[clk_name]
    if not isinstance(clk_node, ClkNode):
        return False
    parent_name, parent_group = parse_source_endpoint(
        clk_node.source, ctx=f"clk {clk_name!r}"
    )
    return parent_name == cpu_gate_name and parent_group == group


def _find_downstream_path(tree: Tree, start: str, target: str) -> List[str] | None:
    if start == target:
        return [start]
    parent_of: Dict[str, str] = {}
    queue = [start]
    seen = {start}
    while queue:
        name = queue.pop(0)
        for child in _downstream_children(tree, name):
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


def _downstream_children(tree: Tree, name: str) -> List[str]:
    children: List[str] = []
    for other_name, other in tree.nodes.items():
        if other_name == name or other.kind == "source":
            continue
        if isinstance(other, MuxNode):
            for arm in other.source.values():
                arm_name, _ = parse_source_endpoint(arm, ctx="child")
                if arm_name == name:
                    children.append(other_name)
            continue
        try:
            parent = parent_port_for_child(tree, other_name)
        except ValueError:
            continue
        if parent.node == name:
            children.append(other_name)
    return children


def _propagate_port_freqs(
    tree: Tree,
    *,
    active: Set[str],
    mux_sel: Dict[str, int],
    ratios: Dict[str, int],
    targets: List[Tuple[str, int]],
) -> Dict[Port, int] | None:
    port_freq: Dict[Port, int] = {}
    for name in tree.nodes:
        if name not in active:
            for port in output_ports(tree, name):
                port_freq[port] = 0
            continue
        node = tree.nodes[name]
        if node.kind == "source":
            port_freq[Port(name, "")] = node.freq
        elif isinstance(node, PllNode):
            if node.pll_kind == "inno":
                group_req = _required_inno_group_hz(
                    tree, name, targets, active, mux_sel, ratios
                )
                for group in node.output_groups:
                    port_freq[Port(name, group)] = group_req.get(group, 0)
            else:
                port_freq[Port(name, "")] = node.freq or 0
        elif isinstance(node, MuxNode):
            sel = mux_sel.get(name, node.sel)
            if sel is None:
                return None
            arm = node.source.get(str(sel))
            if not arm:
                return None
            peer = parse_port_ref(arm, ctx=f"mux {name!r}")
            peer_hz = _resolve_port_freq(
                tree, peer, active, mux_sel, ratios, targets, port_freq
            )
            if peer_hz is None:
                return None
            port_freq[Port(name, "")] = peer_hz
        elif isinstance(node, DivNode):
            parent_port = parent_port_for_child(tree, name)
            f_in = _resolve_port_freq(
                tree, parent_port, active, mux_sel, ratios, targets, port_freq
            )
            if f_in is None or f_in <= 0:
                return None
            required = _required_div_outputs(
                tree, name, targets, active, mux_sel, ratios
            )
            if node.div_kind == "cpu_gate":
                divided_hz = 0
                for port in output_ports(tree, name):
                    if is_cpu_gate_passthrough_group(port.group):
                        continue
                    want = required.get(port.group)
                    if want is not None:
                        divided_hz = want
                        break
                if divided_hz <= 0:
                    ratio = ratios.get(name, node.ratio)
                    if ratio is None:
                        return None
                    f_hw, _ = div_hw_from_input(f_in, ratio)
                    divided_hz = f_hw
                for port in output_ports(tree, name):
                    if is_cpu_gate_passthrough_group(port.group):
                        port_freq[port] = f_in
                    else:
                        port_freq[port] = divided_hz
            else:
                want = required.get("")
                if want is None:
                    return None
                port_freq[Port(name, "")] = want
        elif is_passthrough_kind(node.kind) or isinstance(node, ClkNode):
            parent_port = parent_port_for_child(tree, name)
            parent_hz = _resolve_port_freq(
                tree, parent_port, active, mux_sel, ratios, targets, port_freq
            )
            if parent_hz is None:
                return None
            for port in output_ports(tree, name):
                port_freq[port] = parent_hz
    return port_freq


def _resolve_port_freq(
    tree: Tree,
    port: Port,
    active: Set[str],
    mux_sel: Dict[str, int],
    ratios: Dict[str, int],
    targets: List[Tuple[str, int]],
    cache: Dict[Port, int],
) -> int | None:
    if port in cache:
        return cache[port]
    if port.node not in active:
        cache[port] = 0
        return 0
    node = tree.nodes[port.node]
    if node.kind == "source":
        cache[port] = node.freq
        return node.freq
    if isinstance(node, PllNode):
        if node.pll_kind == "inno":
            reqs = _required_inno_group_hz(
                tree, port.node, targets, active, mux_sel, ratios
            )
            hz = reqs.get(port.group, 0)
        else:
            hz = node.freq or 0
        cache[port] = hz
        return hz
    if isinstance(node, MuxNode):
        sel = mux_sel.get(port.node, node.sel)
        if sel is None:
            return None
        arm = node.source.get(str(sel))
        if not arm:
            return None
        peer = parse_port_ref(arm, ctx=f"mux {port.node!r}")
        hz = _resolve_port_freq(
            tree, peer, active, mux_sel, ratios, targets, cache
        )
        if hz is None:
            return None
        cache[Port(port.node, "")] = hz
        return hz
    if isinstance(node, DivNode):
        parent_port = parent_port_for_child(tree, port.node)
        f_in = _resolve_port_freq(
            tree, parent_port, active, mux_sel, ratios, targets, cache
        )
        if f_in is None:
            return None
        if node.div_kind == "cpu_gate":
            if is_cpu_gate_passthrough_group(port.group):
                cache[port] = f_in
                return f_in
            required = _required_div_outputs(
                tree, port.node, targets, active, mux_sel, ratios
            )
            divided_hz = 0
            for group, hz in required.items():
                if hz > 0:
                    divided_hz = hz
                    break
            if divided_hz <= 0:
                ratio = ratios.get(port.node, node.ratio)
                if ratio is None:
                    return None
                f_hw, _ = div_hw_from_input(f_in, ratio)
                divided_hz = f_hw
            cache[port] = divided_hz
            return divided_hz
        required = _required_div_outputs(
            tree, port.node, targets, active, mux_sel, ratios
        )
        hz = required.get("", 0)
        cache[port] = hz
        return hz
    if is_passthrough_kind(node.kind) or isinstance(node, ClkNode):
        parent_port = parent_port_for_child(tree, port.node)
        hz = _resolve_port_freq(
            tree, parent_port, active, mux_sel, ratios, targets, cache
        )
        if hz is None:
            return None
        cache[port] = hz
        return hz
    return None


def _required_inno_group_hz(
    tree: Tree,
    pll_name: str,
    targets: List[Tuple[str, int]],
    active: Set[str],
    mux_sel: Dict[str, int],
    ratios: Dict[str, int],
) -> Dict[str, int]:
    out: Dict[str, int] = {}
    pll = tree.nodes[pll_name]
    assert isinstance(pll, PllNode)
    for group in pll.output_groups:
        for clk_name, clk_hz in targets:
            if not _clk_reaches_pll_group(tree, pll_name, group, clk_name):
                continue
            req = clk_hz
            path = _find_downstream_path(tree, pll_name, clk_name)
            if path is None:
                continue
            for downstream in reversed(path[1:]):
                node = tree.nodes[downstream]
                if node.kind in ("gate", "inv", "cell", "clk"):
                    continue
                if isinstance(node, MuxNode):
                    continue
                if isinstance(node, DivNode):
                    ratio = node.ratio if node.ratio is not None else ratios.get(downstream)
                    if ratio is None:
                        req = 0
                        break
                    req *= ratio
            if req <= 0:
                continue
            prev = out.get(group)
            if prev is not None and prev != req:
                out[group] = -1
            else:
                out[group] = req
    if pll.freq is not None and pll.freq > 0:
        out.setdefault("0", pll.freq)
    return {k: v for k, v in out.items() if v > 0}


def _clk_reaches_pll_group(
    tree: Tree,
    pll_name: str,
    group: str,
    clk_name: str,
) -> bool:
    path = _find_downstream_path(tree, pll_name, clk_name)
    if path is None:
        return False
    if group:
        first = path[1] if len(path) > 1 else ""
        if first:
            clk_node = tree.nodes[clk_name]
            parent_name, parent_group = parse_source_endpoint(
                clk_node.source, ctx=f"clk {clk_name!r}"
            )
            if parent_name == pll_name:
                return parent_group == group
    return True


def _clk_targets_match(
    targets: List[Tuple[str, int]],
    port_freq: Dict[Port, int],
) -> bool:
    for clk_name, want_hz in targets:
        if port_freq.get(Port(clk_name, "")) != want_hz:
            return False
    return True


def _compute_pll_vars(
    tree: Tree,
    *,
    active: Set[str],
    port_freq: Dict[Port, int],
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> Dict[str, Dict[str, int]] | None:
    pll_vars: Dict[str, Dict[str, int]] = {}
    for name, node in tree.nodes.items():
        if name not in active or not isinstance(node, PllNode):
            continue
        ref_port = parent_port_for_child(tree, name)
        ref_hz = port_freq.get(ref_port, 0)
        if ref_hz <= 0:
            return None
        if node.pll_kind == "inno":
            group_hz = {
                group: port_freq.get(Port(name, group), 0)
                for group in node.output_groups
            }
            coeffs = search_pll_coefficients(
                node.pll_kind,
                ref_hz,
                0,
                fbdiv_min=pll_sc_fbdiv_min,
                fbdiv_max=pll_sc_fbdiv_max,
                tol_lo=tol_lo,
                tol_hi=tol_hi,
                tol_den=tol_den,
                group_out_hz=group_hz,
            )
        else:
            out_hz = port_freq.get(Port(name, ""), node.freq or 0)
            coeffs = search_pll_coefficients(
                node.pll_kind,
                ref_hz,
                out_hz,
                fbdiv_min=pll_sc_fbdiv_min,
                fbdiv_max=pll_sc_fbdiv_max,
                tol_lo=tol_lo,
                tol_hi=tol_hi,
                tol_den=tol_den,
            )
        if coeffs is None:
            return None
        pll_vars[name] = coeffs
    return pll_vars


def _assemble_model(
    tree: Tree,
    *,
    active: Set[str],
    port_freq: Dict[Port, int],
    mux_sel: Dict[str, int],
    ratios: Dict[str, int],
    pll_vars: Dict[str, Dict[str, int]],
) -> SolveModel:
    gate_open: Dict[str, bool] = {}
    for name, node in tree.nodes.items():
        if isinstance(node, GateNode):
            if node.open == 0:
                gate_open[name] = False
            elif node.open == 1:
                gate_open[name] = True
            else:
                gate_open[name] = name in active

    active_map = {name: name in active for name in tree.nodes}
    mux_map = {
        name: sel
        for name, sel in mux_sel.items()
        if isinstance(tree.nodes[name], MuxNode)
    }
    return SolveModel(
        active=active_map,
        port_freq=dict(port_freq),
        ratios=dict(ratios),
        mux_sel=mux_map,
        gate_open=gate_open,
        pll_vars=pll_vars,
    )
