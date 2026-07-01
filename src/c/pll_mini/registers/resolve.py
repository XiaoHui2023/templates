from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from .fit_pll import fit_pll_vars
from .pll_cfg import pll_cfg_from_solved
from model.consolver import solve_tree_with_consolver
from model.solve_model import SolveModel
from load.tools import log_stage_done, log_stage_progress, log_stage_start
from model.verify import raise_on_verify_issues, verify_solve_model

from model.nodes import (
    DivNode,
    GateNode,
    PllNode,
    Tree,
)
from model.freq_graph import Port, output_ports


@dataclass(frozen=True)
class ResolvedNode:
    name: str
    kind: str
    active: bool
    resolved_freq: int
    port_freqs: Dict[str, int]
    ratio: int
    mux_sel: int
    gate_open: bool
    pll_cfg: Dict[str, int]


@dataclass(frozen=True)
class TreeResolve:
    by_name: Dict[str, ResolvedNode]
    clk_names: tuple[str, ...]
    solve_model: SolveModel


def _primary_port_freq(
    node: object,
    port_freqs: Dict[str, int],
) -> int:
    groups = getattr(node, "output_groups", None) or []
    for group in groups:
        if group in port_freqs:
            return port_freqs[group]
    if "" in port_freqs:
        return port_freqs[""]
    if port_freqs:
        return next(iter(port_freqs.values()))
    return 0


def resolve_tree(
    tree: Tree,
    *,
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    period_tolerance: float,
    solve_timeout_ms: int | None = None,
    debug_consolver_smt_path: Path | None = None,
    reg_index: object | None = None,
) -> TreeResolve:
    _ = reg_index
    clk_nodes = [n for n in tree.nodes_ordered if n.kind == "clk"]
    if not clk_nodes:
        raise ValueError("tree 须至少含一个 kind 为 clk 的节点")

    model = solve_tree_with_consolver(
        tree,
        pll_sc_fbdiv_min=pll_sc_fbdiv_min,
        pll_sc_fbdiv_max=pll_sc_fbdiv_max,
        period_tolerance=period_tolerance,
        timeout_ms=solve_timeout_ms,
        debug_smt_path=debug_consolver_smt_path,
    )

    fit_started_at = log_stage_start(
        "resolve",
        "fit",
        "pll coefficients",
        nodes=len(tree.nodes),
    )
    model = fit_pll_vars(
        tree,
        model,
        pll_sc_fbdiv_min=pll_sc_fbdiv_min,
        pll_sc_fbdiv_max=pll_sc_fbdiv_max,
        period_tolerance=period_tolerance,
    )
    log_stage_done(
        "resolve",
        "fit",
        "pll coefficients",
        fit_started_at,
        pll=len(model.pll_vars),
    )

    verify_started_at = log_stage_start(
        "resolve",
        "verify",
        "formula replay",
        nodes=len(tree.nodes),
    )
    issues = verify_solve_model(
        tree, model, period_tolerance=period_tolerance
    )
    raise_on_verify_issues(tree, issues)
    log_stage_done(
        "resolve",
        "verify",
        "formula replay",
        verify_started_at,
        issues=0,
    )

    resolve_started_at = log_stage_start(
        "resolve",
        "nodes",
        "tree",
        nodes=len(tree.nodes),
    )
    resolved: Dict[str, ResolvedNode] = {}
    for index, (node_name, node) in enumerate(tree.nodes.items(), start=1):
        if index == 1 or index % 128 == 0:
            log_stage_progress(
                "resolve",
                "nodes",
                "tree",
                current=index,
                total=len(tree.nodes),
                node=node_name,
            )
        on_path = model.active.get(node_name, False)
        ratio = model.ratios.get(node_name, 0)
        sel = model.mux_sel.get(node_name, 0)
        gate_is_open = model.gate_open.get(node_name, False)
        if isinstance(node, GateNode):
            gate_is_open = on_path and gate_is_open

        pll_cfg: Dict[str, int] = {}
        if isinstance(node, PllNode) and node.regs:
            vars_map = model.pll_vars.get(node_name, {})
            if vars_map:
                pll_cfg = pll_cfg_from_solved(
                    node.pll_kind,
                    vars_map,
                    output_groups=node.output_groups,
                )

        port_freqs: Dict[str, int] = {}
        for port in output_ports(tree, node_name):
            hz = model.port_hz(port)
            key = port.group if port.group else ""
            port_freqs[key] = hz
        primary = _primary_port_freq(node, port_freqs)
        if isinstance(node, PllNode) and node.freq is not None:
            primary = node.freq

        resolved[node_name] = ResolvedNode(
            name=node_name,
            kind=node.kind,
            active=on_path,
            resolved_freq=primary,
            port_freqs=port_freqs,
            ratio=ratio,
            mux_sel=sel,
            gate_open=gate_is_open,
            pll_cfg=pll_cfg,
        )

    log_stage_done(
        "resolve",
        "nodes",
        "tree",
        resolve_started_at,
        nodes=len(resolved),
    )

    return TreeResolve(
        by_name=resolved,
        clk_names=tuple(n.name for n in clk_nodes),
        solve_model=model,
    )
