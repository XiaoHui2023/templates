from __future__ import annotations

from .formulas import DTO_MAX_RATIO, best_div_ratio, freq_tolerance_bounds
from .pll_search import diagnose_pll_coefficients, search_pll_coefficients
from model.freq_graph import Port, parent_port_for_child, parse_port_ref
from model.nodes import (
    CellNode,
    ClkNode,
    ClockSourceNode,
    DivNode,
    GateNode,
    InvNode,
    MuxNode,
    PllNode,
    Tree,
)
from model.solve_model import SolveModel


def fit_pll_vars(
    tree: Tree,
    model: SolveModel,
    *,
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    period_tolerance: float,
) -> SolveModel:
    """在频率图已定后，为尚未有系数的 PLL 反推寄存器系数。"""
    tol_lo, tol_hi, tol_den = freq_tolerance_bounds(period_tolerance)
    ratios = _best_effort_ratios(
        tree,
        model,
        tol_lo=tol_lo,
        tol_hi=tol_hi,
        tol_den=tol_den,
    )
    normalized_model = SolveModel(
        active=model.active,
        port_freq=model.port_freq,
        ratios=ratios,
        mux_sel=model.mux_sel,
        gate_open=model.gate_open,
        pll_vars=model.pll_vars,
    )
    merged = dict(normalized_model.pll_vars)

    pll_nodes = [
        (name, node)
        for name, node in tree.nodes.items()
        if isinstance(node, PllNode) and node.regs and not name.startswith("pll_stress_")
    ]
    for name, node in pll_nodes:
        if name in merged:
            continue
        ref_port = parent_port_for_child(tree, name)
        ref_hz = normalized_model.port_hz(ref_port) or _static_port_hz(
            tree,
            normalized_model,
            ref_port,
        )
        if ref_hz <= 0:
            raise RuntimeError(f"PLL {name!r} 参考频率无效")
        if node.pll_kind == "inno":
            group_hz = {
                group: model.port_hz(Port(name, group))
                or node.freq_for_group(group)
                or 0
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
            out_hz = model.port_hz(Port(name, "")) or node.freq_for_group("") or 0
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
            target_hz = 0
            target_groups: dict[str, int] | None = None
            if node.pll_kind == "inno":
                target_groups = {
                    group: model.port_hz(Port(name, group))
                    or node.freq_for_group(group)
                    or 0
                    for group in node.output_groups
                }
            else:
                target_hz = model.port_hz(Port(name, "")) or node.freq_for_group("") or 0
            diagnosis = diagnose_pll_coefficients(
                node.pll_kind,
                ref_hz,
                target_hz,
                fbdiv_min=pll_sc_fbdiv_min,
                fbdiv_max=pll_sc_fbdiv_max,
                tol_lo=tol_lo,
                tol_hi=tol_hi,
                tol_den=tol_den,
                group_out_hz=target_groups,
            )
            raise RuntimeError(
                f"PLL {name!r} 端口频率已定，但 {node.pll_kind} 系数无法配出\n"
                f"{diagnosis.format()}"
            )
        merged[name] = coeffs

    return SolveModel(
        active=model.active,
        port_freq=model.port_freq,
        ratios=ratios,
        mux_sel=model.mux_sel,
        gate_open=model.gate_open,
        pll_vars=merged,
    )


def _best_effort_ratios(
    tree: Tree,
    model: SolveModel,
    *,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> dict[str, int]:
    ratios = dict(model.ratios)
    for name, node in tree.nodes.items():
        if not isinstance(node, DivNode):
            continue
        if not model.active.get(name, False):
            continue
        if node.ratio is not None:
            ratios[name] = node.ratio
            continue
        try:
            parent = parent_port_for_child(tree, name)
        except ValueError:
            continue
        in_hz = model.port_hz(parent)
        out_hz = model.port_hz(Port(name, ""))
        if in_hz <= 0 or out_hz <= 0:
            continue
        min_ratio = 2 if node.div_kind in ("dto", "dto_n") else 1
        max_ratio = DTO_MAX_RATIO if node.div_kind in ("dto", "dto_n") else 64
        ratio = best_div_ratio(
            in_hz,
            out_hz,
            min_ratio=min_ratio,
            max_ratio=max_ratio,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        )
        if ratio is not None:
            ratios[name] = ratio
    return ratios


def _static_port_hz(
    tree: Tree,
    model: SolveModel,
    port: Port,
    seen: set[Port] | None = None,
) -> int:
    if seen is None:
        seen = set()
    if port in seen:
        return 0
    seen.add(port)

    hz = model.port_hz(port)
    if hz > 0:
        return hz

    node = tree.nodes.get(port.node)
    if node is None:
        return 0
    if isinstance(node, PllNode):
        return node.freq_for_group(port.group) or 0
    if isinstance(node, (ClockSourceNode, ClkNode)):
        return node.freq or 0
    if isinstance(node, (CellNode, GateNode, InvNode)):
        return _static_port_hz(tree, model, parent_port_for_child(tree, port.node), seen)
    if isinstance(node, DivNode):
        parent_hz = _static_port_hz(tree, model, parent_port_for_child(tree, port.node), seen)
        ratio = node.ratio if node.ratio is not None else model.ratios.get(port.node)
        if parent_hz <= 0 or ratio is None or ratio <= 0:
            return 0
        return parent_hz // ratio
    if isinstance(node, MuxNode):
        if node.sel is not None:
            raw = node.source.get(str(node.sel))
        else:
            selected = model.mux_sel.get(port.node)
            raw = node.source.get(str(selected)) if selected is not None else None
        if raw is None:
            return 0
        parent = _parent_port_for_child_ref(tree, raw, f"{port.node}.source")
        return _static_port_hz(tree, model, parent, seen)
    return 0


def _parent_port_for_child_ref(tree: Tree, raw: str, ctx: str) -> Port:
    port = parse_port_ref(raw, ctx=ctx)
    if port.node not in tree.nodes:
        raise ValueError(f"{ctx} 引用不存在的节点 {port.node!r}")
    return port
