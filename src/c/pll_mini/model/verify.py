from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from registers.formulas import (
    div_hw_from_input,
    freq_tolerance_bounds,
    freq_within_tolerance,
    pll_dw_actual_hz,
    pll_inno_actual_hz,
    pll_sc_actual_hz,
    pll_tci_actual_hz,
)
from .freq_graph import (
    Port,
    collect_freq_targets,
    collect_non_freq_constraint_clks,
    is_passthrough_kind,
    node_has_upstream_ref,
    output_ports,
    parent_port_for_child,
    port_label,
    parse_port_ref,
    walk_path_upstream,
)
from .nodes import CellNode, ClkNode, ClockSourceNode, DivNode, GateNode, InvNode, MuxNode, PllNode, Tree
from .solve_model import SolveModel


@dataclass(frozen=True)
class VerifyIssue:
    headline: str
    formula: str
    detail: str
    path_nodes: tuple[str, ...]


def _hz_mhz(hz: int) -> str:
    if hz % 1_000_000 == 0:
        return f"{hz // 1_000_000} MHz"
    if hz % 1_000 == 0:
        return f"{hz / 1_000:.3f} kHz"
    return f"{hz} Hz"


def _path_for_edge(tree: Tree, child: str, clk_name: str) -> tuple[str, ...]:
    chain = walk_path_upstream(tree, clk_name)
    if child in chain:
        idx = chain.index(child)
        return tuple(reversed(chain[idx:]))
    return (child,)


def verify_solve_model(
    tree: Tree,
    model: SolveModel,
    *,
    period_tolerance: float,
) -> List[VerifyIssue]:
    issues: List[VerifyIssue] = []
    tol_lo, tol_hi, tol_den = freq_tolerance_bounds(period_tolerance)
    targets = collect_freq_targets(tree)
    non_constraint_clks = frozenset(collect_non_freq_constraint_clks(tree))

    for clk_name, want_hz in targets:
        port = Port(clk_name, "")
        got_hz = model.port_hz(port)
        if got_hz != want_hz:
            issues.append(
                VerifyIssue(
                    headline=f"clk {clk_name} 频率与目标不一致",
                    formula="f_clk = 目标频率",
                    detail=(
                        f"目标 {_hz_mhz(want_hz)}，"
                        f"模型 {_hz_mhz(got_hz)}"
                    ),
                    path_nodes=(clk_name,),
                )
            )

    for name, node in tree.nodes.items():
        if not model.active.get(name, False):
            continue

        if isinstance(node, DivNode):
            ratio = model.ratios.get(name, 0)
            if ratio < 1:
                continue
            parent_port = parent_port_for_child(tree, name)
            f_in = model.port_hz(parent_port)
            f_out = model.port_hz(Port(name, ""))
            try:
                f_hw, rem = div_hw_from_input(f_in, ratio)
            except ValueError:
                issues.append(
                    VerifyIssue(
                        headline=f"div {name} 分频公式不成立",
                        formula="f_ref = f_hw × ratio + rem，0 ≤ rem < ratio",
                        detail=f"f_ref={_hz_mhz(f_in)}，ratio={ratio}",
                        path_nodes=tuple(
                            _path_for_edge(tree, name, targets[0][0])
                        )
                        if targets
                        else (name,),
                    )
                )
                continue
            if not freq_within_tolerance(
                f_out, f_hw, tol_lo=tol_lo, tol_hi=tol_hi, tol_den=tol_den
            ):
                issues.append(
                    VerifyIssue(
                        headline=f"div {name} 输出超出容差",
                        formula=(
                            "f_hw = f_ref // ratio；"
                            f"f_out 在 f_hw 的 ±{period_tolerance * 100:g}% 内"
                        ),
                        detail=(
                            f"f_ref={_hz_mhz(f_in)}，ratio={ratio}，"
                            f"f_hw={_hz_mhz(f_hw)}，rem={rem}，"
                            f"f_out={_hz_mhz(f_out)}"
                        ),
                        path_nodes=tuple(
                            _path_for_edge(tree, name, targets[0][0])
                        )
                        if targets
                        else (name,),
                    )
                )

        if isinstance(node, PllNode):
            vars_map = model.pll_vars.get(name, {})
            if not vars_map:
                continue
            ref_port = parent_port_for_child(tree, name)
            f_ref = model.port_hz(ref_port) or _static_port_hz(tree, model, ref_port)
            kind = node.pll_kind
            if kind == "tci":
                clkf = vars_map.get("clkf", 0)
                f_actual = pll_tci_actual_hz(f_ref, clkf)
                f_out = model.port_hz(Port(name, ""))
                if f_actual != f_out:
                    issues.append(
                        _pll_issue(
                            name,
                            "tci",
                            "f_out = f_ref × clkf",
                            f_ref,
                            f_out,
                            f_actual,
                            clkf=clkf,
                            path=_path_for_edge(
                                tree, name, targets[0][0]
                            )
                            if targets
                            else (name,),
                        )
                    )
            elif kind == "sc":
                fbdiv = vars_map.get("fbdiv", 0)
                refdiv = vars_map.get("refdiv", 0)
                p1 = vars_map.get("postdiv1", 0)
                p2 = vars_map.get("postdiv2", 0)
                f_actual = pll_sc_actual_hz(f_ref, fbdiv, refdiv, p1, p2)
                f_out = model.port_hz(Port(name, ""))
                if not freq_within_tolerance(
                    f_out, f_actual, tol_lo=tol_lo, tol_hi=tol_hi, tol_den=tol_den
                ):
                    issues.append(
                        _pll_issue(
                            name,
                            "sc",
                            "f_out ≈ f_ref×fbdiv/(refdiv×postdiv1×postdiv2)",
                            f_ref,
                            f_out,
                            f_actual,
                            fbdiv=fbdiv,
                            refdiv=refdiv,
                            postdiv1=p1,
                            postdiv2=p2,
                            path=_path_for_edge(
                                tree, name, targets[0][0]
                            )
                            if targets
                            else (name,),
                        )
                    )
            elif kind == "dw":
                fbdiv = vars_map.get("fbdiv", 0)
                p = vars_map.get("p", 0)
                f_actual = pll_dw_actual_hz(f_ref, fbdiv, p)
                f_out = model.port_hz(Port(name, ""))
                if not freq_within_tolerance(
                    f_out, f_actual, tol_lo=tol_lo, tol_hi=tol_hi, tol_den=tol_den
                ):
                    issues.append(
                        _pll_issue(
                            name,
                            "dw",
                            "f_out ≈ f_ref×fbdiv/(p+1)",
                            f_ref,
                            f_out,
                            f_actual,
                            fbdiv=fbdiv,
                            p=p,
                            path=_path_for_edge(
                                tree, name, targets[0][0]
                            )
                            if targets
                            else (name,),
                        )
                    )
            elif kind == "inno":
                fbdiv = vars_map.get("fbdiv", 0)
                refdiv = vars_map.get("refdiv", 0)
                for port in output_ports(tree, name):
                    p1 = vars_map.get(f"postdiv1_{port.group}", 0)
                    p2 = vars_map.get(f"postdiv2_{port.group}", 0)
                    f_actual = pll_inno_actual_hz(
                        f_ref, fbdiv, refdiv, p1, p2
                    )
                    f_out = model.port_hz(port)
                    if f_out <= 0:
                        continue
                    if not freq_within_tolerance(
                        f_out,
                        f_actual,
                        tol_lo=tol_lo,
                        tol_hi=tol_hi,
                        tol_den=tol_den,
                    ):
                        issues.append(
                            _pll_issue(
                                name,
                                f"inno[{port.group}]",
                                "f_out ≈ f_ref×fbdiv/(refdiv×postdiv1×postdiv2)",
                                f_ref,
                                f_out,
                                f_actual,
                                fbdiv=fbdiv,
                                refdiv=refdiv,
                                postdiv1=p1,
                                postdiv2=p2,
                                path=_path_for_edge(
                                    tree, name, targets[0][0]
                                )
                                if targets
                                else (name,),
                            )
                        )

        if is_passthrough_kind(node.kind):
            if not node_has_upstream_ref(node):
                continue
            parent_port = parent_port_for_child(tree, name)
            f_parent = model.port_hz(parent_port)
            out_ports = output_ports(tree, name)
            if not out_ports:
                continue
            f_self = model.port_hz(out_ports[0])
            if f_parent != f_self:
                issues.append(
                    VerifyIssue(
                        headline=f"{node.kind} {name} 未透传前级频率",
                        formula="f_out = f_ref",
                        detail=(
                            f"前级 {port_label(parent_port, tree)} "
                            f"{_hz_mhz(f_parent)}，"
                            f"本节点 {_hz_mhz(f_self)}"
                        ),
                        path_nodes=tuple(
                            _path_for_edge(tree, name, targets[0][0])
                        )
                        if targets
                        else (name,),
                    )
                )

        if isinstance(node, ClkNode):
            if name in non_constraint_clks:
                continue
            if not node_has_upstream_ref(node):
                continue
            parent_port = parent_port_for_child(tree, name)
            if model.port_hz(Port(name, "")) != model.port_hz(parent_port):
                issues.append(
                    VerifyIssue(
                        headline=f"clk {name} 与前级频率不一致",
                        formula="f_clk = f_ref",
                        detail=(
                            f"前级 {_hz_mhz(model.port_hz(parent_port))}，"
                            f"clk {_hz_mhz(model.port_hz(Port(name, '')))}"
                        ),
                        path_nodes=walk_path_upstream(tree, name),
                    )
                )

    return issues


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
    if isinstance(node, (ClockSourceNode, ClkNode, PllNode)):
        return node.freq or 0
    if isinstance(node, (CellNode, GateNode, InvNode)):
        return _static_port_hz(tree, model, parent_port_for_child(tree, port.node), seen)
    if isinstance(node, DivNode):
        parent_hz = _static_port_hz(tree, model, parent_port_for_child(tree, port.node), seen)
        if parent_hz <= 0 or node.ratio is None:
            return 0
        return parent_hz // node.ratio
    if isinstance(node, MuxNode):
        if node.sel is not None:
            raw = node.source.get(str(node.sel))
        else:
            selected = model.mux_sel.get(port.node)
            raw = node.source.get(str(selected)) if selected is not None else None
        if raw is None:
            return 0
        parent = parse_port_ref(raw, ctx=f"{port.node}.source")
        return _static_port_hz(tree, model, parent, seen)
    return 0


def _pll_issue(
    name: str,
    kind_label: str,
    formula: str,
    f_ref: int,
    f_out: int,
    f_actual: int,
    *,
    path: tuple[str, ...],
    **coeffs: int,
) -> VerifyIssue:
    coeff_text = "，".join(f"{key}={value}" for key, value in coeffs.items())
    return VerifyIssue(
        headline=f"pll {name} {kind_label} 系数与频率不一致",
        formula=formula,
        detail=(
            f"f_ref={_hz_mhz(f_ref)}，f_out={_hz_mhz(f_out)}，"
            f"按系数算得 f_actual={_hz_mhz(f_actual)}"
            + (f"；{coeff_text}" if coeff_text else "")
        ),
        path_nodes=path,
    )


def raise_on_verify_issues(
    tree: Tree,
    issues: Sequence[VerifyIssue],
) -> None:
    if not issues:
        return
    from report.diagnose import diagnostic_from_verify, format_verify_issues, print_diagnostic_report

    diag = [diagnostic_from_verify(item) for item in issues]
    print_diagnostic_report(tree, issues=diag)
    text = format_verify_issues(issues)
    raise ValueError(f"{text}\n\n路径子树见 stderr。")
