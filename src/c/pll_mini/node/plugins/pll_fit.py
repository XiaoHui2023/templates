from __future__ import annotations

from model.arithmetic import freq_tolerance_bounds
from model.freq_graph import Port, parent_port_for_child
from model.freq_graph import static_port_hz as _static_port_hz
from model.nodes import Tree
from model.solve_model import SolveModel

from .pll_search import diagnose_pll_coefficients, search_pll_coefficients


def fit_node(
    node,
    tree: Tree,
    model: SolveModel,
    *,
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    period_tolerance: float,
) -> SolveModel:
    """在频率图已定后，为尚未有系数的 PLL 反推寄存器系数。"""
    tol_lo, tol_hi, tol_den = freq_tolerance_bounds(period_tolerance)
    normalized_model = model
    merged = model.values(node.name)
    pll_nodes = [(node.name, node)] if node.regs else []
    for name, node in pll_nodes:
        if "coefficients" in merged:
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
                target_hz = (
                    model.port_hz(Port(name, "")) or node.freq_for_group("") or 0
                )
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
        merged["coefficients"] = coeffs

    return model
