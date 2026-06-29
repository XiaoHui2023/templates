from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterator, List, Set, Tuple

from registers.formulas import (
    CPU_GATE_RATIOS,
    DTO_MAX_RATIO,
    div_hw_from_input,
    dto_ratio_candidates_for_pair,
    find_div_ratio,
    freq_tolerance_bounds,
)
from model.freq_graph import (
    Port,
    backward_required_nodes,
    backward_required_nodes_bounded,
    backward_required_nodes_pll_ref,
    collect_freq_targets,
    is_cpu_gate_passthrough_group,
    is_mux_exclusive_peer,
    is_passthrough_kind,
    is_static_frequency_anchor_node,
    is_static_frequency_anchor,
    output_ports,
    parent_port_for_child,
    parse_port_ref,
)
from model.nodes import (
    ClkNode,
    DivNode,
    GateNode,
    MuxNode,
    PllNode,
    Tree,
    parse_source_endpoint,
)
from registers.pll_search import pll_ref_hz_candidates, search_pll_coefficients
from model.solve_model import SolveModel
from load.tools import log_stage_done, log_stage_start
from model.topology import bind_tree_topology, clear_tree_topology
from search.progress import ComponentSearchReporter


@dataclass(frozen=True)
class SearchComponent:
    """一次顺序求解的子树：按固定频率边界切分后的最小求解单元。"""

    index: int
    total: int
    targets: tuple[tuple[str, int], ...]
    node_names: frozenset[str]
    freq_anchors: frozenset[str] = frozenset()
    pll_ref_for: str | None = None


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
    bind_tree_topology(tree)
    try:
        components = partition_search_components(tree, targets)
        from report.ui import active_progress_session

        progress = active_progress_session()
        if progress is not None:
            progress.show_partition_preview(tree, components)
        partition_started = log_stage_start(
            "search",
            "partition",
            "clock components",
            components=len(components),
        )
        comp_labels = "; ".join(_component_log_label(c) for c in components)
        log_stage_done(
            "search",
            "partition",
            "clock components",
            partition_started,
            components=len(components),
            trees=comp_labels,
        )
        partial_models: List[SolveModel] = []
        for component in components:
            if progress is not None:
                progress.show_active_component(tree, component)
            comp_started = log_stage_start(
                "search",
                "component",
                f"{component.index}/{component.total}",
                clks=_component_label(component),
            )
            if deadline is not None and time.perf_counter() > deadline:
                log_stage_done(
                    "search",
                    "component",
                    f"{component.index}/{component.total}",
                    comp_started,
                    failed=True,
                    progress=f"{component.index - 1}/{component.total}",
                )
                raise RuntimeError("时钟树约束求解超时或无法判定")
            try:
                if component.pll_ref_for is not None:
                    partial = _search_pll_ref_tree(
                        tree,
                        pll_name=component.pll_ref_for,
                        required=set(component.node_names),
                        pll_sc_fbdiv_min=pll_sc_fbdiv_min,
                        pll_sc_fbdiv_max=pll_sc_fbdiv_max,
                        tol_lo=tol_lo,
                        tol_hi=tol_hi,
                        tol_den=tol_den,
                        deadline=deadline,
                        compute_pll_vars=_pll_ref_needs_coeffs(
                            tree, component.pll_ref_for
                        ),
                    )
                else:
                    partial = _search_tree(
                        tree,
                        targets=list(component.targets),
                        required=set(component.node_names),
                        pll_anchors=_non_inno_pll_anchors(
                            tree, component.freq_anchors
                        ),
                        pll_sc_fbdiv_min=pll_sc_fbdiv_min,
                        pll_sc_fbdiv_max=pll_sc_fbdiv_max,
                        tol_lo=tol_lo,
                        tol_hi=tol_hi,
                        tol_den=tol_den,
                        deadline=deadline,
                    )
            except RuntimeError as exc:
                log_stage_done(
                    "search",
                    "component",
                    f"{component.index}/{component.total}",
                    comp_started,
                    failed=True,
                    progress=f"{component.index - 1}/{component.total}",
                )
                _raise_component_failure(
                    tree,
                    component=component,
                    period_tolerance=period_tolerance,
                    cause=exc,
                )
            log_stage_done(
                "search",
                "component",
                f"{component.index}/{component.total}",
                comp_started,
                status="ok",
                progress=f"{component.index}/{component.total}",
            )
            partial_models.append(partial)
        merge_started = log_stage_start(
            "search",
            "merge",
            "component models",
            components=len(partial_models),
        )
        try:
            model = merge_solve_models(tree, partial_models)
            model = _recompute_merged_pll_vars(
                tree,
                model,
                pll_sc_fbdiv_min=pll_sc_fbdiv_min,
                pll_sc_fbdiv_max=pll_sc_fbdiv_max,
                tol_lo=tol_lo,
                tol_hi=tol_hi,
                tol_den=tol_den,
            )
        except RuntimeError as exc:
            log_stage_done(
                "search",
                "merge",
                "component models",
                merge_started,
                failed=True,
                progress=f"{len(partial_models)}/{len(components)}",
            )
            _raise_merge_failure(
                tree,
                components=components,
                period_tolerance=period_tolerance,
                cause=exc,
            )
        log_stage_done(
            "search",
            "merge",
            "component models",
            merge_started,
            progress=f"{len(partial_models)}/{len(components)}",
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
    finally:
        clear_tree_topology()
    log_stage_done(
        "search",
        "solve",
        "tree constraints",
        started_at,
        model_items=len(model.port_freq),
        components=len(components),
    )
    return model


def partition_search_components(
    tree: Tree,
    targets: List[Tuple[str, int]],
) -> List[SearchComponent]:
    """按固定频率边界切最小 clk 子树，合并共享可变节点的目标，并补 PLL 参考路径子树。"""
    if not targets:
        return []

    clk_components: List[SearchComponent] = []
    plls_for_ref: Set[str] = set()
    for clk_name, hz in sorted(targets, key=lambda item: item[0]):
        required = backward_required_nodes_bounded(tree, [(clk_name, hz)])
        anchors = frozenset(
            name
            for name in required
            if is_static_frequency_anchor_node(tree, name)
        )
        for name in required:
            node = tree.nodes[name]
            if isinstance(node, PllNode):
                plls_for_ref.add(name)
        clk_components.append(
            SearchComponent(
                index=0,
                total=0,
                targets=((clk_name, hz),),
                node_names=frozenset(required),
                freq_anchors=anchors,
            )
        )

    merged_clk = _merge_overlapping_clk_components(tree, clk_components)

    ref_components: List[SearchComponent] = []
    for pll_name in sorted(plls_for_ref):
        ref_required = backward_required_nodes_pll_ref(tree, pll_name)
        if len(ref_required) <= 1:
            continue
        ref_components.append(
            SearchComponent(
                index=0,
                total=0,
                targets=(),
                node_names=frozenset(ref_required),
                pll_ref_for=pll_name,
            )
        )

    combined = ref_components + merged_clk
    total = len(combined)
    return [
        SearchComponent(
            index=index,
            total=total,
            targets=comp.targets,
            node_names=comp.node_names,
            freq_anchors=comp.freq_anchors,
            pll_ref_for=comp.pll_ref_for,
        )
        for index, comp in enumerate(combined, start=1)
    ]


def _non_inno_pll_anchors(
    tree: Tree,
    anchors: frozenset[str],
) -> frozenset[str]:
    return frozenset(
        name
        for name in anchors
        if isinstance(tree.nodes.get(name), PllNode)
        and tree.nodes[name].pll_kind != "inno"
    )


def _pll_ref_needs_coeffs(tree: Tree, pll_name: str) -> bool:
    node = tree.nodes.get(pll_name)
    return isinstance(node, PllNode) and node.pll_kind != "inno"


def verify_search_partition(tree: Tree) -> int:
    """验收：每个 clk 目标恰落在某一 clk 子树内，并返回子树总数。"""
    targets = collect_freq_targets(tree)
    components = partition_search_components(tree, targets)
    if not components:
        raise RuntimeError("时钟树子树划分为空")
    clk_components = [c for c in components if c.pll_ref_for is None]
    cover: Dict[str, int] = {}
    for comp in clk_components:
        for clk_name, _hz in comp.targets:
            cover[clk_name] = cover.get(clk_name, 0) + 1
    for clk_name, _hz in targets:
        if cover.get(clk_name, 0) != 1:
            raise RuntimeError(
                f"clk 节点 {clk_name!r} 应恰出现在一个 clk 子树中，"
                f"实际 {cover.get(clk_name, 0)} 次"
            )
    return len(components)


def _mutable_component_nodes(tree: Tree, node_names: Set[str] | frozenset[str]) -> Set[str]:
    return {
        name
        for name in node_names
        if not is_static_frequency_anchor_node(tree, name)
    }


def _merge_overlapping_clk_components(
    tree: Tree,
    components: List[SearchComponent],
) -> List[SearchComponent]:
    """合并共享非锚点节点的 clk 子树，避免同一 div/mux 被独立求解出冲突配置。"""
    if len(components) <= 1:
        return components

    parent = list(range(len(components)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    mutable_sets = [
        _mutable_component_nodes(tree, comp.node_names) for comp in components
    ]
    for left in range(len(components)):
        for right in range(left + 1, len(components)):
            if mutable_sets[left] & mutable_sets[right]:
                union(left, right)

    groups: Dict[int, List[int]] = defaultdict(list)
    for index in range(len(components)):
        groups[find(index)].append(index)

    merged: List[SearchComponent] = []
    for indices in groups.values():
        if len(indices) == 1:
            merged.append(components[indices[0]])
            continue
        all_nodes: Set[str] = set()
        all_anchors: Set[str] = set()
        all_targets: List[Tuple[str, int]] = []
        seen_targets: Set[Tuple[str, int]] = set()
        for index in indices:
            comp = components[index]
            all_nodes |= comp.node_names
            all_anchors |= comp.freq_anchors
            for target in comp.targets:
                if target not in seen_targets:
                    seen_targets.add(target)
                    all_targets.append(target)
        merged.append(
            SearchComponent(
                index=0,
                total=0,
                targets=tuple(all_targets),
                node_names=frozenset(all_nodes),
                freq_anchors=frozenset(all_anchors),
            )
        )
    merged.sort(key=lambda comp: comp.targets[0][0] if comp.targets else "")
    return merged


def merge_solve_models(tree: Tree, models: List[SolveModel]) -> SolveModel:
    if not models:
        raise RuntimeError("时钟树约束互相矛盾，无解")
    if len(models) == 1:
        return models[0]

    active: Dict[str, bool] = {name: False for name in tree.nodes}
    port_freq: Dict[Port, int] = {}
    mux_sel: Dict[str, int] = {}
    ratios: Dict[str, int] = {}
    gate_open: Dict[str, bool] = {}
    pll_vars: Dict[str, Dict[str, int]] = {}

    for partial in models:
        for name, on in partial.active.items():
            if on:
                active[name] = True
        for port, hz in partial.port_freq.items():
            if partial.active.get(port.node, False):
                port_freq[port] = hz
        for name, sel in partial.mux_sel.items():
            if partial.active.get(name, False):
                mux_sel[name] = sel
        for name, ratio in partial.ratios.items():
            if partial.active.get(name, False):
                ratios[name] = ratio
        for name, opened in partial.gate_open.items():
            if partial.active.get(name, False):
                gate_open[name] = opened
        for name, coeffs in partial.pll_vars.items():
            if partial.active.get(name, False):
                pll_vars[name] = coeffs

    for name in tree.nodes:
        if name not in active:
            active[name] = False
        for port in output_ports(tree, name):
            if port not in port_freq:
                port_freq[port] = 0
        node = tree.nodes[name]
        if isinstance(node, GateNode) and name not in gate_open:
            if node.open == 0:
                gate_open[name] = False
            elif node.open == 1:
                gate_open[name] = True
            else:
                gate_open[name] = active.get(name, False)

    return SolveModel(
        active=active,
        port_freq=port_freq,
        ratios=ratios,
        mux_sel=mux_sel,
        gate_open=gate_open,
        pll_vars=pll_vars,
    )


def _recompute_merged_pll_vars(
    tree: Tree,
    model: SolveModel,
    *,
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> SolveModel:
    active = {name for name, on in model.active.items() if on}
    pll_vars = _compute_pll_vars(
        tree,
        active=active,
        port_freq=model.port_freq,
        pll_sc_fbdiv_min=pll_sc_fbdiv_min,
        pll_sc_fbdiv_max=pll_sc_fbdiv_max,
        tol_lo=tol_lo,
        tol_hi=tol_hi,
        tol_den=tol_den,
    )
    if pll_vars is None:
        raise RuntimeError("合并后端口频率无法配出合法 PLL 系数")
    return SolveModel(
        active=model.active,
        port_freq=model.port_freq,
        ratios=model.ratios,
        mux_sel=model.mux_sel,
        gate_open=model.gate_open,
        pll_vars=pll_vars,
    )


def _component_clk_names(component: SearchComponent) -> str:
    return ",".join(name for name, _ in component.targets)


def _component_label(component: SearchComponent) -> str:
    if component.pll_ref_for is not None:
        return f"pll_ref:{component.pll_ref_for}"
    return _component_clk_names(component)


def _component_log_label(component: SearchComponent) -> str:
    if component.pll_ref_for is not None:
        return (
            f"[{component.index}] pll_ref={component.pll_ref_for} "
            f"nodes={len(component.node_names)}"
        )
    return (
        f"[{component.index}] clks={_component_clk_names(component)} "
        f"nodes={len(component.node_names)}"
    )


def _raise_component_failure(
    tree: Tree,
    *,
    component: SearchComponent,
    period_tolerance: float,
    cause: RuntimeError,
) -> None:
    from report.diagnose import format_search_component_failure

    clks = _component_clk_names(component)
    headline = (
        f"子树 {component.index}/{component.total} 求解失败"
        f"（clk: {clks}）: {cause}"
    )
    detail = format_search_component_failure(
        tree,
        period_tolerance=period_tolerance,
        component_index=component.index,
        component_total=component.total,
        component_targets=list(component.targets),
        component_nodes=set(component.node_names),
    )
    if detail:
        raise RuntimeError(f"{headline}\n\n{detail}") from cause
    raise RuntimeError(headline) from cause


def _raise_merge_failure(
    tree: Tree,
    *,
    components: List[SearchComponent],
    period_tolerance: float,
    cause: RuntimeError,
) -> None:
    targets: List[Tuple[str, int]] = []
    nodes: Set[str] = set()
    for component in components:
        targets.extend(component.targets)
        nodes.update(component.node_names)
    component = SearchComponent(
        index=1,
        total=1,
        targets=tuple(targets),
        node_names=frozenset(nodes),
    )
    headline = f"子树合并后求解失败：{cause}"
    from report.diagnose import format_search_component_failure

    detail = format_search_component_failure(
        tree,
        period_tolerance=period_tolerance,
        component_index=component.index,
        component_total=component.total,
        component_targets=list(component.targets),
        component_nodes=set(component.node_names),
    )
    if detail:
        raise RuntimeError(f"{headline}\n\n{detail}") from cause
    raise RuntimeError(headline) from cause


def _collect_inno_ref_path_vars(
    tree: Tree,
    active: Set[str],
) -> Tuple[List[str], List[str]]:
    ref_muxes: List[str] = []
    ref_divs: List[str] = []
    mux_seen: Set[str] = set()
    div_seen: Set[str] = set()
    for pll_name in sorted(active):
        node = tree.nodes.get(pll_name)
        if not isinstance(node, PllNode) or node.pll_kind != "inno":
            continue
        ref_name, _ = parse_source_endpoint(node.source, ctx=f"{pll_name}.source")
        name = ref_name
        visited: Set[str] = set()
        while name not in visited:
            visited.add(name)
            if name not in active:
                break
            ref_node = tree.nodes[name]
            if isinstance(ref_node, MuxNode):
                if ref_node.sel is None and name not in mux_seen:
                    mux_seen.add(name)
                    ref_muxes.append(name)
            elif isinstance(ref_node, DivNode):
                if (
                    ref_node.ratio is None
                    and ref_node.div_kind != "div_r"
                    and name not in div_seen
                ):
                    div_seen.add(name)
                    ref_divs.append(name)
            if ref_node.kind == "source":
                break
            try:
                parent_port = parent_port_for_child(tree, name)
            except ValueError:
                break
            name = parent_port.node
    return ref_muxes, ref_divs


def _search_tree(
    tree: Tree,
    *,
    targets: List[Tuple[str, int]],
    required: Set[str] | None = None,
    pll_anchors: frozenset[str] = frozenset(),
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
    deadline: float | None,
) -> SolveModel:
    if required is None:
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

    reporter = ComponentSearchReporter(tree, free_muxes)
    try:
        for assignment in _iter_mux_assignments(
            tree, free_muxes, targets=targets, fixed_mux_sel=mux_sel
        ):
            reporter.mux_trial(assignment)
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
            ref_muxes, ref_divs = _collect_inno_ref_path_vars(tree, active)
            ref_mux_free = [
                name
                for name in ref_muxes
                if isinstance(tree.nodes[name], MuxNode) and tree.nodes[name].sel is None
            ]
            ref_mux_iters = _iter_mux_assignments(
                tree, ref_mux_free, targets=targets, fixed_mux_sel=trial_mux
            )
            pll_name = _ref_path_pll_name(tree, ref_divs)
            solved = False
            reporter.set_trial_mux(trial_mux)
            if ref_mux_free:
                reporter.begin_ref_mux(tree, ref_mux_free)
            for ref_mux_assignment in ref_mux_iters:
                if ref_mux_free:
                    reporter.ref_mux_trial(ref_mux_assignment)
                trial_mux_full = {**trial_mux, **ref_mux_assignment}
                active_full = _compute_active(tree, targets, trial_mux_full)
                if not _active_covers_targets(
                    tree, targets, active_full, trial_mux_full
                ):
                    continue
                ref_div_iter = _iter_ref_div_ratio_assignments(
                    tree,
                    ref_divs,
                    trial_ratios,
                    pll_name=pll_name,
                    targets=targets,
                    active=active_full,
                    mux_sel=trial_mux_full,
                    pll_sc_fbdiv_min=pll_sc_fbdiv_min,
                    pll_sc_fbdiv_max=pll_sc_fbdiv_max,
                    tol_lo=tol_lo,
                    tol_hi=tol_hi,
                    tol_den=tol_den,
                )
                for ref_ratio_pack in ref_div_iter:
                    trial_ratios_full = {**trial_ratios, **ref_ratio_pack}
                    port_freq = _propagate_port_freqs(
                        tree,
                        active=active_full,
                        mux_sel=trial_mux_full,
                        ratios=trial_ratios_full,
                        targets=targets,
                        ref_path=bool(ref_divs),
                    )
                    if port_freq is None:
                        continue
                    if not _clk_targets_match(targets, port_freq):
                        continue
                    pll_vars = _compute_pll_vars(
                        tree,
                        active=active_full,
                        port_freq=port_freq,
                        pll_sc_fbdiv_min=pll_sc_fbdiv_min,
                        pll_sc_fbdiv_max=pll_sc_fbdiv_max,
                        tol_lo=tol_lo,
                        tol_hi=tol_hi,
                        tol_den=tol_den,
                        skip_pll_names=pll_anchors,
                    )
                    if pll_vars is None:
                        continue
                    model = _assemble_model(
                        tree,
                        active=active_full,
                        port_freq=port_freq,
                        mux_sel=trial_mux_full,
                        ratios=trial_ratios_full,
                        pll_vars=pll_vars,
                        export_nodes=required,
                    )
                    solved = True
                    break
                if solved:
                    break
            if solved:
                return model
    finally:
        reporter.end()

    raise RuntimeError("时钟树约束互相矛盾，无解")


def _search_pll_ref_tree(
    tree: Tree,
    *,
    pll_name: str,
    required: Set[str],
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
    deadline: float | None,
    compute_pll_vars: bool = True,
) -> SolveModel:
    free_muxes = _free_mux_nodes(tree, required)
    ref_divs = _ordered_ref_path_div_nodes(tree, required, pll_name)

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

    reporter = ComponentSearchReporter(tree, free_muxes, pll_ref=True)
    try:
        for assignment in _iter_mux_assignments(
            tree, free_muxes, fixed_mux_sel=mux_sel
        ):
            reporter.mux_trial(assignment)
            if deadline is not None and time.perf_counter() > deadline:
                raise RuntimeError("时钟树约束求解超时或无法判定")
            trial_mux = {**mux_sel, **assignment}
            active = _compute_active_pll_ref(tree, pll_name, trial_mux) & required
            if pll_name not in active:
                continue
            for trial_ratios in _iter_ref_div_ratio_assignments(
                tree,
                ref_divs,
                ratios,
                pll_name=pll_name,
                targets=[],
                active=active,
                mux_sel=trial_mux,
                pll_sc_fbdiv_min=pll_sc_fbdiv_min,
                pll_sc_fbdiv_max=pll_sc_fbdiv_max,
                tol_lo=tol_lo,
                tol_hi=tol_hi,
                tol_den=tol_den,
            ):
                port_freq = _propagate_port_freqs(
                    tree,
                    active=active,
                    mux_sel=trial_mux,
                    ratios=trial_ratios,
                    targets=[],
                    ref_path=True,
                )
                if port_freq is None:
                    continue
                if compute_pll_vars:
                    pll_vars = _compute_pll_vars(
                        tree,
                        active=active,
                        port_freq=port_freq,
                        pll_sc_fbdiv_min=pll_sc_fbdiv_min,
                        pll_sc_fbdiv_max=pll_sc_fbdiv_max,
                        tol_lo=tol_lo,
                        tol_hi=tol_hi,
                        tol_den=tol_den,
                        only_pll_names=frozenset({pll_name}),
                    )
                    if pll_vars is None or pll_name not in pll_vars:
                        continue
                else:
                    ref_port = parent_port_for_child(tree, pll_name)
                    if port_freq.get(ref_port, 0) <= 0:
                        continue
                    pll_vars = {}
                return _assemble_model(
                    tree,
                    active=active,
                    port_freq=port_freq,
                    mux_sel=trial_mux,
                    ratios=trial_ratios,
                    pll_vars=pll_vars,
                    export_nodes=required,
                )
    finally:
        reporter.end()

    raise RuntimeError("时钟树约束互相矛盾，无解")


def _compute_active_pll_ref(
    tree: Tree,
    pll_name: str,
    mux_sel: Dict[str, int],
) -> Set[str]:
    pll = tree.nodes[pll_name]
    assert isinstance(pll, PllNode)
    ref_name, _ = parse_source_endpoint(pll.source, ctx=f"{pll_name}.source")
    active: Set[str] = set()
    _mark_upstream_active(tree, ref_name, active, mux_sel)
    active.add(pll_name)
    return active


def _ordered_ref_path_div_nodes(
    tree: Tree,
    required: Set[str],
    pll_name: str,
) -> List[str]:
    free = _ordered_ref_path_div_nodes_unsorted(tree, required, pll_name)

    def depth_to_pll(name: str) -> int:
        path = _find_downstream_path(tree, name, pll_name)
        return len(path) if path else 0

    return sorted(free, key=depth_to_pll, reverse=True)


def _ordered_ref_path_div_nodes_unsorted(
    tree: Tree,
    required: Set[str],
    pll_name: str,
) -> List[str]:
    out: List[str] = []
    for name in sorted(required):
        if name == pll_name:
            continue
        node = tree.nodes[name]
        if not isinstance(node, DivNode):
            continue
        if node.ratio is not None or node.div_kind == "div_r":
            continue
        out.append(name)
    return out


def _ref_path_pll_name(tree: Tree, ref_divs: List[str]) -> str | None:
    for name, node in tree.nodes.items():
        if isinstance(node, PllNode) and node.pll_kind == "inno":
            for div_name in ref_divs:
                if _find_downstream_path(tree, div_name, name) is not None:
                    return name
    return None


def _iter_ref_div_ratio_assignments(
    tree: Tree,
    ref_divs: List[str],
    base_ratios: Dict[str, int],
    *,
    pll_name: str | None,
    targets: List[Tuple[str, int]],
    active: Set[str],
    mux_sel: Dict[str, int],
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> Iterator[Dict[str, int]]:
    if not ref_divs:
        yield dict(base_ratios)
        return

    ordered = list(ref_divs)
    if pll_name is not None:

        def depth_to_pll(name: str) -> int:
            path = _find_downstream_path(tree, name, pll_name)
            return len(path) if path else 0

        ordered = sorted(ref_divs, key=depth_to_pll, reverse=True)

    div_name = ordered[0]
    rest = ordered[1:]
    candidates = _ref_div_ratio_candidates(
        tree,
        div_name,
        pll_name=pll_name,
        targets=targets,
        active=active,
        mux_sel=mux_sel,
        base_ratios=base_ratios,
        pll_sc_fbdiv_min=pll_sc_fbdiv_min,
        pll_sc_fbdiv_max=pll_sc_fbdiv_max,
        tol_lo=tol_lo,
        tol_hi=tol_hi,
        tol_den=tol_den,
    )
    if not candidates:
        return

    for ratio in candidates:
        trial = {**base_ratios, div_name: ratio}
        yield from _iter_ref_div_ratio_assignments(
            tree,
            rest,
            trial,
            pll_name=pll_name,
            targets=targets,
            active=active,
            mux_sel=mux_sel,
            pll_sc_fbdiv_min=pll_sc_fbdiv_min,
            pll_sc_fbdiv_max=pll_sc_fbdiv_max,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        )


def _ref_div_ratio_candidates(
    tree: Tree,
    div_name: str,
    *,
    pll_name: str | None,
    targets: List[Tuple[str, int]],
    active: Set[str],
    mux_sel: Dict[str, int],
    base_ratios: Dict[str, int],
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> List[int]:
    node = tree.nodes[div_name]
    assert isinstance(node, DivNode)
    if node.ratio is not None:
        return [node.ratio]
    if node.div_kind == "div_r":
        return []

    f_in = _ref_parent_hz_for_div(tree, div_name, active, mux_sel, base_ratios)
    if f_in is None or f_in <= 0:
        return []

    want_outs: tuple[int, ...] = ()
    if pll_name is not None:
        want_outs = _ref_div_want_out_candidates(
            tree,
            div_name,
            pll_name,
            targets=targets,
            active=active,
            mux_sel=mux_sel,
            ratios=base_ratios,
            pll_sc_fbdiv_min=pll_sc_fbdiv_min,
            pll_sc_fbdiv_max=pll_sc_fbdiv_max,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        )

    found: List[int] = []
    if node.div_kind in ("div", "div_n"):
        scan = want_outs or (0,)
        for want_out in scan:
            if want_out <= 0:
                for ratio in range(1, 65):
                    if ratio not in found:
                        found.append(ratio)
                break
            ratio = find_div_ratio(
                f_in,
                want_out,
                range(1, 65),
                tol_lo=tol_lo,
                tol_hi=tol_hi,
                tol_den=tol_den,
            )
            if ratio is not None and ratio not in found:
                found.append(ratio)
        return found or list(range(1, 65))
    if node.div_kind == "cpu_gate":
        scan = want_outs or (0,)
        for want_out in scan:
            if want_out <= 0:
                return sorted(CPU_GATE_RATIOS)
            ratio = find_div_ratio(
                f_in,
                want_out,
                sorted(CPU_GATE_RATIOS),
                tol_lo=tol_lo,
                tol_hi=tol_hi,
                tol_den=tol_den,
            )
            if ratio is not None and ratio not in found:
                found.append(ratio)
        return found or sorted(CPU_GATE_RATIOS)
    if node.div_kind in ("dto", "dto_n"):
        if pll_name is None:
            return list(range(2, min(65, DTO_MAX_RATIO + 1)))
        found = []
        for ratio in range(2, min(65, DTO_MAX_RATIO + 1)):
            f_hw, _ = div_hw_from_input(f_in, ratio)
            if _pll_accepts_ref_hz(
                tree,
                pll_name,
                f_hw,
                targets=targets,
                active=active,
                mux_sel=mux_sel,
                ratios=base_ratios,
                pll_sc_fbdiv_min=pll_sc_fbdiv_min,
                pll_sc_fbdiv_max=pll_sc_fbdiv_max,
                tol_lo=tol_lo,
                tol_hi=tol_hi,
                tol_den=tol_den,
            ):
                found.append(ratio)
        if not found and want_outs:
            for want_out in want_outs[:16]:
                for ratio in dto_ratio_candidates_for_pair(
                    f_in,
                    want_out,
                    tol_lo=tol_lo,
                    tol_hi=tol_hi,
                    tol_den=tol_den,
                ):
                    if ratio not in found:
                        found.append(ratio)
        return found
    return []


def _ref_div_want_out_candidates(
    tree: Tree,
    div_name: str,
    pll_name: str,
    *,
    targets: List[Tuple[str, int]],
    active: Set[str],
    mux_sel: Dict[str, int],
    ratios: Dict[str, int],
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> tuple[int, ...]:
    pll = tree.nodes[pll_name]
    assert isinstance(pll, PllNode)
    if pll.pll_kind == "inno":
        _ = (
            pll_sc_fbdiv_min,
            pll_sc_fbdiv_max,
            tol_lo,
            tol_hi,
            tol_den,
        )
        return ()
    else:
        out_hz = pll.freq or 0
        ref_cands = pll_ref_hz_candidates(
            pll.pll_kind,
            out_hz=out_hz,
            fbdiv_min=pll_sc_fbdiv_min,
            fbdiv_max=pll_sc_fbdiv_max,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        )
    if not ref_cands:
        return ()

    path = _find_downstream_path(tree, div_name, pll_name)
    if path is None:
        return ref_cands

    want_outs: set[int] = set()
    idx = path.index(div_name)
    for ref_hz in ref_cands:
        hz = ref_hz
        for downstream in reversed(path[idx + 1 :]):
            if downstream == pll_name:
                continue
            dnode = tree.nodes[downstream]
            if not isinstance(dnode, DivNode):
                continue
            ratio = dnode.ratio if dnode.ratio is not None else ratios.get(downstream)
            if ratio is None:
                hz = 0
                break
            hz *= ratio
        if hz > 0:
            want_outs.add(hz)
    cands = tuple(sorted(want_outs))
    if len(cands) > 24:
        step = max(1, len(cands) // 24)
        cands = cands[::step][:24]
    return cands


def _ref_parent_hz_for_div(
    tree: Tree,
    div_name: str,
    active: Set[str],
    mux_sel: Dict[str, int],
    ratios: Dict[str, int],
) -> int | None:
    parent_port = parent_port_for_child(tree, div_name)
    return _ref_hz_at_port(tree, parent_port, active, mux_sel, ratios)


def _ref_hz_at_port(
    tree: Tree,
    port: Port,
    active: Set[str],
    mux_sel: Dict[str, int],
    ratios: Dict[str, int],
) -> int | None:
    if port.node not in active:
        return None
    node = tree.nodes[port.node]
    if node.kind == "source":
        return node.freq
    if isinstance(node, MuxNode):
        sel = mux_sel.get(port.node, node.sel)
        if sel is None:
            return None
        arm = node.source.get(str(sel))
        if not arm:
            return None
        peer = parse_port_ref(arm, ctx=f"mux {port.node!r}")
        return _ref_hz_at_port(tree, peer, active, mux_sel, ratios)
    if isinstance(node, DivNode):
        parent_port = parent_port_for_child(tree, port.node)
        f_in = _ref_hz_at_port(tree, parent_port, active, mux_sel, ratios)
        if f_in is None or f_in <= 0:
            return None
        ratio = node.ratio if node.ratio is not None else ratios.get(port.node)
        if ratio is None:
            return None
        f_hw, _ = div_hw_from_input(f_in, ratio)
        if node.div_kind == "cpu_gate" and is_cpu_gate_passthrough_group(
            port.group
        ):
            return f_in
        return f_hw
    if is_passthrough_kind(node.kind):
        parent_port = parent_port_for_child(tree, port.node)
        return _ref_hz_at_port(tree, parent_port, active, mux_sel, ratios)
    return None


def _pll_accepts_ref_hz(
    tree: Tree,
    pll_name: str,
    ref_hz: int,
    *,
    targets: List[Tuple[str, int]],
    active: Set[str],
    mux_sel: Dict[str, int],
    ratios: Dict[str, int],
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> bool:
    if ref_hz <= 0:
        return False
    pll = tree.nodes[pll_name]
    if not isinstance(pll, PllNode):
        return False
    if pll.pll_kind == "inno":
        group_hz = _required_inno_group_hz(
            tree, pll_name, targets, active, mux_sel, ratios
        )
        if not group_hz:
            return True
        return ref_hz > 0 and all(hz > 0 for hz in group_hz.values())
    out_hz = pll.freq or 0
    if out_hz <= 0:
        return False
    return (
        search_pll_coefficients(
            pll.pll_kind,
            ref_hz,
            out_hz,
            fbdiv_min=pll_sc_fbdiv_min,
            fbdiv_max=pll_sc_fbdiv_max,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        )
        is not None
    )


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
    *,
    targets: List[Tuple[str, int]] | None = None,
    fixed_mux_sel: Dict[str, int] | None = None,
) -> Iterator[Dict[str, int]]:
    fixed = fixed_mux_sel or {}

    def recurse(rest: List[str], partial: Dict[str, int]) -> Iterator[Dict[str, int]]:
        if not rest:
            if targets and not _mux_assignments_compatible(
                tree, targets, {**fixed, **partial}
            ):
                return
            yield partial
            return

        mux_name = rest[0]
        node = tree.nodes[mux_name]
        assert isinstance(node, MuxNode)
        keys = sorted(node.source.keys(), key=lambda k: int(k))
        for key in keys:
            trial = {**partial, mux_name: int(key)}
            yield from recurse(rest[1:], trial)

    if not free_muxes:
        yield {}
        return
    yield from recurse(free_muxes, {})


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
        if isinstance(node, PllNode):
            if node.pll_kind == "inno":
                return chain
            if node.freq is not None and node.freq > 0:
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
        if is_static_frequency_anchor(tree, parent_name, via_port=parent_port):
            return chain
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
    for name in list(active):
        node = tree.nodes[name]
        if isinstance(node, PllNode) and node.pll_kind == "inno":
            ref_name, _ = parse_source_endpoint(node.source, ctx=f"{name}.source")
            _mark_upstream_active(tree, ref_name, active, mux_sel)
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
    from model.topology import active_tree_topology

    topo = active_tree_topology()
    if topo is not None:
        path = topo.find_downstream_path(start, target)
        return list(path) if path is not None else None
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
    from model.topology import active_tree_topology

    topo = active_tree_topology()
    if topo is not None:
        return list(topo.downstream_children(name))
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
    ref_path: bool = False,
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
                tree, peer, active, mux_sel, ratios, targets, port_freq,
                ref_path=ref_path,
            )
            if peer_hz is None:
                return None
            port_freq[Port(name, "")] = peer_hz
        elif isinstance(node, DivNode):
            parent_port = parent_port_for_child(tree, name)
            f_in = _resolve_port_freq(
                tree, parent_port, active, mux_sel, ratios, targets, port_freq,
                ref_path=ref_path,
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
                if ref_path:
                    ratio = ratios.get(name, node.ratio)
                    if ratio is None:
                        return None
                    f_hw, _ = div_hw_from_input(f_in, ratio)
                    port_freq[Port(name, "")] = f_hw
                elif want is None:
                    return None
                else:
                    port_freq[Port(name, "")] = want
        elif is_passthrough_kind(node.kind) or isinstance(node, ClkNode):
            parent_port = parent_port_for_child(tree, name)
            parent_hz = _resolve_port_freq(
                tree, parent_port, active, mux_sel, ratios, targets, port_freq,
                ref_path=ref_path,
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
    *,
    ref_path: bool = False,
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
            tree, peer, active, mux_sel, ratios, targets, cache,
            ref_path=ref_path,
        )
        if hz is None:
            return None
        cache[Port(port.node, "")] = hz
        return hz
    if isinstance(node, DivNode):
        parent_port = parent_port_for_child(tree, port.node)
        f_in = _resolve_port_freq(
            tree, parent_port, active, mux_sel, ratios, targets, cache,
            ref_path=ref_path,
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
        if ref_path:
            ratio = ratios.get(port.node, node.ratio)
            if ratio is None:
                return None
            f_hw, _ = div_hw_from_input(f_in, ratio)
            hz = f_hw
        else:
            hz = required.get("", 0)
            if hz <= 0:
                return None
        cache[port] = hz
        return hz
    if is_passthrough_kind(node.kind) or isinstance(node, ClkNode):
        parent_port = parent_port_for_child(tree, port.node)
        hz = _resolve_port_freq(
            tree, parent_port, active, mux_sel, ratios, targets, cache,
            ref_path=ref_path,
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
            if not _clk_reaches_pll_group(
                tree, pll_name, group, clk_name, mux_sel
            ):
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
    mux_sel: Dict[str, int],
) -> bool:
    chain = _walk_upstream(tree, clk_name, mux_sel)
    if chain is None or pll_name not in chain:
        return False
    idx = chain.index(pll_name)
    if idx <= 0:
        return False
    upstream = chain[idx - 1]
    upstream_node = tree.nodes[upstream]
    if isinstance(upstream_node, MuxNode):
        sel = mux_sel.get(upstream, upstream_node.sel)
        if sel is None:
            return False
        arm = upstream_node.source.get(str(sel))
        if not arm:
            return False
        dev, grp = parse_source_endpoint(arm, ctx=f"mux {upstream!r}")
        return dev == pll_name and grp == group
    try:
        parent_port = parent_port_for_child(tree, upstream)
    except ValueError:
        return False
    return parent_port.node == pll_name and parent_port.group == group


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
    skip_pll_names: frozenset[str] = frozenset(),
    only_pll_names: frozenset[str] | None = None,
) -> Dict[str, Dict[str, int]] | None:
    pll_vars: Dict[str, Dict[str, int]] = {}
    for name, node in tree.nodes.items():
        if name not in active or not isinstance(node, PllNode):
            continue
        if name in skip_pll_names:
            continue
        if only_pll_names is not None and name not in only_pll_names:
            continue
        ref_port = parent_port_for_child(tree, name)
        ref_hz = port_freq.get(ref_port, 0)
        if ref_hz <= 0:
            return None
        if node.pll_kind == "inno":
            continue
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
    export_nodes: Set[str],
) -> SolveModel:
    gate_open: Dict[str, bool] = {}
    for name, node in tree.nodes.items():
        if name not in export_nodes:
            continue
        if isinstance(node, GateNode):
            if node.open == 0:
                gate_open[name] = False
            elif node.open == 1:
                gate_open[name] = True
            else:
                gate_open[name] = name in active

    active_map = {name: False for name in tree.nodes}
    for name in export_nodes:
        if name in active:
            active_map[name] = True
    mux_map = {
        name: sel
        for name, sel in mux_sel.items()
        if name in export_nodes and isinstance(tree.nodes[name], MuxNode)
    }
    export_port_freq = {
        port: hz
        for port, hz in port_freq.items()
        if port.node in export_nodes
    }
    export_ratios = {
        name: ratio for name, ratio in ratios.items() if name in export_nodes
    }
    export_pll_vars = {
        name: coeffs
        for name, coeffs in pll_vars.items()
        if name in export_nodes
    }
    return SolveModel(
        active=active_map,
        port_freq=export_port_freq,
        ratios=export_ratios,
        mux_sel=mux_map,
        gate_open=gate_open,
        pll_vars=export_pll_vars,
    )
