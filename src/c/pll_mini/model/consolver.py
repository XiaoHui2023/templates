from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from load.tools import log_stage_done, log_stage_start, run_consolver_solve
from registers.formulas import DTO_MAX_RATIO
from registers.formulas import (
    freq_tolerance_bounds,
)

from .freq_graph import Port, output_ports, parent_port_for_child
from .nodes import ClkNode, DivNode, GateNode, MuxNode, PllNode, Tree
from .solve_model import SolveModel


@dataclass(frozen=True)
class NamedConstraint:
    name: str
    expr: str


def solve_tree_with_consolver(
    tree: Tree,
    *,
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    period_tolerance: float,
    timeout_ms: int | None = None,
    debug_smt_path: Path | None = None,
) -> SolveModel:
    builder = _SmtBuilder(
        tree,
        pll_sc_fbdiv_min=pll_sc_fbdiv_min,
        pll_sc_fbdiv_max=pll_sc_fbdiv_max,
        period_tolerance=period_tolerance,
    )
    smt2 = builder.render()
    if debug_smt_path is not None:
        debug_started_at = log_stage_start(
            "resolve",
            "smt",
            "debug",
            path=debug_smt_path,
        )
        debug_smt_path.parent.mkdir(parents=True, exist_ok=True)
        debug_smt_path.write_text(smt2, encoding="utf-8")
        log_stage_done(
            "resolve",
            "smt",
            "debug",
            debug_started_at,
            bytes=debug_smt_path.stat().st_size,
        )

    started_at = log_stage_start(
        "resolve",
        "smt",
        "build",
        constraints=len(builder.constraints),
    )
    log_stage_done(
        "resolve",
        "smt",
        "build",
        started_at,
        constraints=len(builder.constraints),
    )
    raw = run_consolver_solve(smt2, timeout_ms=timeout_ms)

    data = json.loads(raw)
    status = data.get("status")
    if status != "sat":
        detail = _format_unsolved(status, data, builder.constraints)
        raise RuntimeError(detail)
    model = data.get("model")
    if not isinstance(model, dict):
        raise RuntimeError("consolver 输出缺少 model 对象")
    return builder.to_solve_model(model)


def build_tree_smt2(
    tree: Tree,
    *,
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    period_tolerance: float,
) -> str:
    builder = _SmtBuilder(
        tree,
        pll_sc_fbdiv_min=pll_sc_fbdiv_min,
        pll_sc_fbdiv_max=pll_sc_fbdiv_max,
        period_tolerance=period_tolerance,
    )
    return builder.render()


class _SmtBuilder:
    def __init__(
        self,
        tree: Tree,
        *,
        pll_sc_fbdiv_min: int,
        pll_sc_fbdiv_max: int,
        period_tolerance: float,
    ) -> None:
        self.tree = tree
        self.pll_sc_fbdiv_min = pll_sc_fbdiv_min
        self.pll_sc_fbdiv_max = pll_sc_fbdiv_max
        self.tol_lo, self.tol_hi, self.tol_den = freq_tolerance_bounds(period_tolerance)
        self.constraints: List[NamedConstraint] = []
        self.decls: Dict[str, str] = {}
        self._build()

    def render(self) -> str:
        lines = ["(set-logic ALL)", "(set-option :produce-models true)"]
        for name in sorted(self.decls):
            lines.append(f"(declare-const {name} {self.decls[name]})")
        for item in self.constraints:
            lines.append(f"(assert (! {item.expr} :named {item.name}))")
        lines.extend(["(check-sat)", "(get-model)", ""])
        return "\n".join(lines)

    def to_solve_model(self, model: dict[str, object]) -> SolveModel:
        active: Dict[str, bool] = {}
        port_freq: Dict[Port, int] = {}
        ratios: Dict[str, int] = {}
        mux_sel: Dict[str, int] = {}
        gate_open: Dict[str, bool] = {}
        pll_vars: Dict[str, Dict[str, int]] = {}

        for name, node in self.tree.nodes.items():
            active[name] = bool(model.get(_act(name), False))
            if isinstance(node, DivNode):
                ratios[name] = int(model.get(_ratio(name), node.ratio or 0))
            if isinstance(node, MuxNode):
                mux_sel[name] = int(model.get(_sel(name), node.sel or 0))
            if isinstance(node, GateNode):
                gate_open[name] = active[name]
            if isinstance(node, PllNode) and active[name]:
                keys = _pll_var_keys(node)
                if keys and all(_pll_var(name, key) in model for key in keys):
                    pll_vars[name] = {
                    key: int(model.get(_pll_var(name, key), 0))
                    for key in _pll_var_keys(node)
                    }
            for port in output_ports(self.tree, name):
                port_freq[port] = int(model.get(_freq(port), 0))

        return SolveModel(
            active=active,
            port_freq=port_freq,
            ratios=ratios,
            mux_sel=mux_sel,
            gate_open=gate_open,
            pll_vars=pll_vars,
        )

    def _build(self) -> None:
        for name in self.tree.nodes:
            self._declare(_act(name), "Bool")
            for port in output_ports(self.tree, name):
                self._declare(_freq(port), "Int")

        for name, node in self.tree.nodes.items():
            self._common_node_constraints(name)
            if node.kind == "source":
                self._source_constraints(name)
            elif isinstance(node, ClkNode):
                self._single_input_equal_constraints(name, target=True)
            elif isinstance(node, GateNode):
                self._single_input_equal_constraints(name)
            elif node.kind in ("inv", "cell"):
                self._single_input_equal_constraints(name)
            elif isinstance(node, DivNode):
                self._div_constraints(name, node)
            elif isinstance(node, PllNode):
                self._pll_constraints(name, node)
            elif isinstance(node, MuxNode):
                self._mux_constraints(name, node)

    def _common_node_constraints(self, name: str) -> None:
        node = self.tree.nodes[name]
        act = _act(name)
        for port in output_ports(self.tree, name):
            freq = _freq(port)
            self._add(f"{name}__freq_non_negative__{_port_suffix(port)}", f"(>= {freq} 0)")
            self._add(f"{name}__inactive_zero__{_port_suffix(port)}", f"(=> (not {act}) (= {freq} 0))")
            if not (isinstance(node, PllNode) and port.group):
                self._add(f"{name}__active_positive__{_port_suffix(port)}", f"(=> {act} (> {freq} 0))")
            elif port.group and node.freq is None:
                consumers = self._port_consumer_exprs(port)
                if consumers:
                    self._add(
                        f"{name}__unused_zero__{_port_suffix(port)}",
                        f"(=> (not (or {' '.join(consumers)})) (= {freq} 0))",
                    )
                else:
                    self._add(
                        f"{name}__unused_zero__{_port_suffix(port)}",
                        f"(= {freq} 0)",
                    )
            fixed = getattr(node, "freq", None)
            if fixed is not None and (not port.group or isinstance(node, PllNode)):
                self._add(
                    f"{name}__fixed_freq__{_port_suffix(port)}",
                    f"(=> {act} (= {freq} {fixed}))",
                )

    def _source_constraints(self, name: str) -> None:
        node = self.tree.nodes[name]
        fixed = getattr(node, "freq", None)
        if fixed is not None:
            self._add(name + "__source_freq", f"(=> {_act(name)} (= {_freq(Port(name, ''))} {fixed}))")

    def _single_input_equal_constraints(self, name: str, *, target: bool = False) -> None:
        act = _act(name)
        port = Port(name, "")
        try:
            parent = parent_port_for_child(self.tree, name)
        except ValueError:
            if target:
                node = self.tree.nodes[name]
                if getattr(node, "freq", None) is not None:
                    self._add(f"{name}__target_active", act)
            return
        self._add(f"{name}__parent_active", f"(=> {act} {_act(parent.node)})")
        self._add(f"{name}__freq_equal_parent", f"(=> {act} (= {_freq(port)} {_freq(parent)}))")
        node = self.tree.nodes[name]
        if target and isinstance(node, ClkNode) and node.freq is not None and node.freq > 0:
            self._add(f"{name}__target_active", act)
            self._add(f"{name}__target_freq", f"(= {_freq(port)} {node.freq})")

    def _div_constraints(self, name: str, node: DivNode) -> None:
        act = _act(name)
        ratio = _ratio(name)
        self._declare(ratio, "Int")
        try:
            parent = parent_port_for_child(self.tree, name)
        except ValueError:
            self._add(f"{name}__no_source_inactive", f"(not {act})")
            return
        out = _freq(Port(name, ""))
        self._add(f"{name}__parent_active", f"(=> {act} {_act(parent.node)})")
        min_ratio = 2 if node.div_kind in ("dto", "dto_n") else 1
        self._add(f"{name}__ratio_min", f"(=> {act} (>= {ratio} {min_ratio}))")
        if node.ratio is not None:
            self._add(f"{name}__ratio_fixed", f"(=> {act} (= {ratio} {node.ratio}))")
        elif node.div_kind in ("dto", "dto_n"):
            self._add(f"{name}__ratio_max", f"(=> {act} (<= {ratio} {DTO_MAX_RATIO}))")
        else:
            self._add(f"{name}__ratio_max", f"(=> {act} (<= {ratio} 64))")
        hw = f"(div {_freq(parent)} {ratio})"
        self._add(
            f"{name}__freq_div",
            (
                f"(=> {act} (and "
                f"(<= (* {out} {self.tol_lo}) (* {hw} {self.tol_den})) "
                f"(>= (* {out} {self.tol_hi}) (* {hw} {self.tol_den}))"
                f"))"
            ),
        )

    def _pll_constraints(self, name: str, node: PllNode) -> None:
        act = _act(name)
        if node.regs:
            try:
                parent = parent_port_for_child(self.tree, name)
            except ValueError:
                parent = None
            if parent is not None:
                self._add(f"{name}__parent_active", f"(=> {act} {_act(parent.node)})")
        if node.freq is not None:
            for port in output_ports(self.tree, name):
                self._add(
                    f"{name}__pll_freq__{_port_suffix(port)}",
                    f"(=> {act} (= {_freq(port)} {node.freq}))",
                )

    def _mux_constraints(self, name: str, node: MuxNode) -> None:
        act = _act(name)
        sel = _sel(name)
        self._declare(sel, "Int")
        source_by_sel = {int(key): value for key, value in node.source.items()}
        keys = sorted(source_by_sel)
        if not keys:
            self._add(f"{name}__no_source_inactive", f"(not {act})")
            return
        if node.sel is not None:
            self._add(f"{name}__sel_fixed", f"(=> {act} (= {sel} {node.sel}))")
        else:
            choices = " ".join(f"(= {sel} {key})" for key in keys)
            self._add(f"{name}__sel_inside", f"(=> {act} (or {choices}))")
        for key in keys:
            parent = parent_port_for_child_ref(self.tree, source_by_sel[key], f"{name}.source[{key}]")
            when = f"(and {act} (= {sel} {key}))"
            self._add(f"{name}__arm_{key}__parent_active", f"(=> {when} {_act(parent.node)})")
            self._add(
                f"{name}__arm_{key}__freq",
                f"(=> {when} (= {_freq(Port(name, ''))} {_freq(parent)}))",
            )

    def _declare(self, name: str, typ: str) -> None:
        self.decls[name] = typ

    def _add(self, name: str, expr: str) -> None:
        safe = _safe_name(name)
        self.constraints.append(NamedConstraint(safe, expr))

    def _port_consumer_exprs(self, port: Port) -> list[str]:
        consumers: list[str] = []
        for child_name, child in self.tree.nodes.items():
            if isinstance(child, MuxNode):
                for key, raw in child.source.items():
                    ref = parent_port_for_child_ref(
                        self.tree,
                        raw,
                        f"{child_name}.source[{key}]",
                    )
                    if ref == port:
                        consumers.append(f"(and {_act(child_name)} (= {_sel(child_name)} {int(key)}))")
                continue
            if child.kind == "source":
                continue
            try:
                ref = parent_port_for_child(self.tree, child_name)
            except ValueError:
                continue
            if ref == port:
                consumers.append(_act(child_name))
        return consumers


def parent_port_for_child_ref(tree: Tree, raw: str, ctx: str) -> Port:
    from .freq_graph import parse_port_ref

    port = parse_port_ref(raw, ctx=ctx)
    if port.node not in tree.nodes:
        raise ValueError(f"{ctx} 引用不存在的节点 {port.node!r}")
    return port


def _format_unsolved(
    status: object,
    data: dict[str, object],
    constraints: Iterable[NamedConstraint],
) -> str:
    reason = data.get("reason")
    lines = [f"consolver 求解失败: status={status}"]
    if reason:
        lines.append(f"reason={reason}")
    lines.append("相关命名约束:")
    for item in list(constraints)[:80]:
        lines.append(f"- {item.name}: {item.expr}")
    return "\n".join(lines)


def _act(node: str) -> str:
    return _safe_name(f"act__{node}")


def _ratio(node: str) -> str:
    return _safe_name(f"ratio__{node}")


def _sel(node: str) -> str:
    return _safe_name(f"sel__{node}")


def _pll_var(node: str, key: str) -> str:
    return _safe_name(f"pll__{node}__{key}")


def _pll_var_keys(node: PllNode) -> tuple[str, ...]:
    if node.pll_kind == "tci":
        return ("clkf",)
    if node.pll_kind == "sc":
        return ("fbdiv", "refdiv", "postdiv1", "postdiv2")
    if node.pll_kind == "dw":
        return ("fbdiv", "p")
    if node.pll_kind == "inno":
        keys = ["refdiv", "fbdiv"]
        for group in node.output_groups:
            keys.append(f"postdiv1_{group}")
            keys.append(f"postdiv2_{group}")
        return tuple(keys)
    return ()


def _freq(port: Port) -> str:
    suffix = port.group if port.group else "out"
    return _safe_name(f"freq__{port.node}__{suffix}")


def _port_suffix(port: Port) -> str:
    return port.group if port.group else "out"


def _safe_name(raw: str) -> str:
    out = []
    for ch in raw:
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append("_")
    return "".join(out)
