from __future__ import annotations

from .formulas import freq_tolerance_bounds
from model.freq_graph import Port, parent_port_for_child
from model.nodes import PllNode, Tree
from model.solve_model import SolveModel

from .pll_search import search_pll_coefficients
from load.tools import log_stage_progress


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
    merged = dict(model.pll_vars)
    active = {name for name, on in model.active.items() if on}

    pll_nodes = [
        (name, node)
        for name, node in tree.nodes.items()
        if name in active and isinstance(node, PllNode)
    ]
    for index, (name, node) in enumerate(pll_nodes, start=1):
        log_stage_progress(
            "resolve",
            "fit",
            "pll coefficients",
            current=index,
            total=len(pll_nodes),
            pll=name,
            kind=node.pll_kind,
        )
        if name in merged:
            continue
        ref_port = parent_port_for_child(tree, name)
        ref_hz = model.port_hz(ref_port)
        if ref_hz <= 0:
            raise RuntimeError(f"PLL {name!r} 参考频率无效")
        if node.pll_kind == "inno":
            group_hz = {
                group: model.port_hz(Port(name, group))
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
                progress=(
                    lambda current, total, detail, name=name, kind=node.pll_kind: (
                        log_stage_progress(
                            "resolve",
                            "fit",
                            "pll coefficients",
                            pll=name,
                            kind=kind,
                            current=current,
                            total=total,
                            detail=detail,
                        )
                    )
                ),
            )
        else:
            out_hz = model.port_hz(Port(name, "")) or node.freq or 0
            coeffs = search_pll_coefficients(
                node.pll_kind,
                ref_hz,
                out_hz,
                fbdiv_min=pll_sc_fbdiv_min,
                fbdiv_max=pll_sc_fbdiv_max,
                tol_lo=tol_lo,
                tol_hi=tol_hi,
                tol_den=tol_den,
                progress=(
                    lambda current, total, detail, name=name, kind=node.pll_kind: (
                        log_stage_progress(
                            "resolve",
                            "fit",
                            "pll coefficients",
                            pll=name,
                            kind=kind,
                            current=current,
                            total=total,
                            detail=detail,
                        )
                    )
                ),
            )
        if coeffs is None:
            raise RuntimeError(
                f"PLL {name!r} 端口频率已定，但 {node.pll_kind} 系数无法配出"
            )
        merged[name] = coeffs

    return SolveModel(
        active=model.active,
        port_freq=model.port_freq,
        ratios=model.ratios,
        mux_sel=model.mux_sel,
        gate_open=model.gate_open,
        pll_vars=merged,
    )
