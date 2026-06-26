from __future__ import annotations

import re
from typing import Dict, List, Mapping, Tuple

from formulas import DTO_MAX_RATIO
from nodes import (
    ClkNode,
    DivNode,
    GateNode,
    MuxNode,
    PllNode,
    Tree,
    parse_source_endpoint,
)
from reg_paths import CPU_GATE_PASS_THROUGH_GROUP
from diagnose import (
    collect_debug_issues,
    format_debug_issues_summary,
    print_diagnostic_report,
)
from tools import log_stage_done, log_stage_start, run_consolver_solve

_SMT_SAFE = re.compile(r"[^a-zA-Z0-9_]")
_FREQ_TOL_DEN = 100
_DIAG_SKIP_LINES = frozenset({"(check-sat)", "(get-model)"})


def _sym(node_name: str, suffix: str) -> str:
    base = _SMT_SAFE.sub("_", node_name)
    if base and base[0].isdigit():
        base = f"n_{base}"
    return f"{suffix}_{base}"


def _track(*parts: str) -> str:
    raw = "_".join(parts)
    track = _SMT_SAFE.sub("_", raw)
    if track and track[0].isdigit():
        track = f"t_{track}"
    return track


def _ite_chain(pairs: List[Tuple[str, str]], default: str) -> str:
    if not pairs:
        return default
    expr = default
    for cond, val in reversed(pairs):
        expr = f"(ite {cond} {val} {expr})"
    return expr


def _freq_tolerance_bounds(period_tolerance: float) -> tuple[int, int, int]:
    tol_num = round(period_tolerance * _FREQ_TOL_DEN)
    return _FREQ_TOL_DEN - tol_num, _FREQ_TOL_DEN + tol_num, _FREQ_TOL_DEN


def _div_needs_ratio_var(node: DivNode) -> bool:
    return node.div_kind in ("div", "div_n", "dto", "dto_n", "cpu_gate")


def _finite_ratio_values(node: DivNode) -> tuple[int, ...] | None:
    if node.ratio is not None:
        return (node.ratio,)
    if node.div_kind in ("div", "div_n"):
        return tuple(range(1, 65))
    if node.div_kind == "cpu_gate":
        return (2, 3, 4, 6)
    return None


class _Smt2Builder:
    def __init__(self) -> None:
        self._declarations: List[str] = []
        self._constraints: List[tuple[str, str | None, str | None]] = []

    def declare(self, text: str) -> None:
        self._declarations.append(text)

    def constraint(
        self,
        expr: str,
        *,
        track: str | None = None,
        hint: str | None = None,
    ) -> None:
        self._constraints.append((expr, track, hint))

    def _render(self, *, named_tracks: bool) -> str:
        lines: List[str] = []
        if named_tracks:
            lines.append("(set-option :produce-unsat-cores true)")
        lines.append("(set-logic QF_LIA)")
        lines.extend(self._declarations)
        for expr, track, _hint in self._constraints:
            if named_tracks and track is not None:
                lines.append(f"(assert (! {expr} :named {track}))")
            else:
                lines.append(f"(assert {expr})")
        lines.append("(check-sat)")
        lines.append("(get-model)")
        return "\n".join(lines) + "\n"

    def finish(
        self,
    ) -> tuple[str, str, Dict[str, str], List[tuple[str, str, str]]]:
        hints = {
            track: hint
            for _expr, track, hint in self._constraints
            if track is not None and hint is not None
        }
        tracked = [
            (track, expr, hint)
            for expr, track, hint in self._constraints
            if track is not None and hint is not None
        ]
        return (
            self._render(named_tracks=False),
            self._render(named_tracks=True),
            hints,
            tracked,
        )

def _div_freq_constraint_expr(
    *,
    active: str,
    freq_in: str,
    freq_out: str,
    ratio: str,
    freq_hw: str,
    rem: str,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> str:
    relation = _div_freq_relation_expr(
        freq_in=freq_in,
        freq_out=freq_out,
        ratio=ratio,
        freq_hw=freq_hw,
        rem=rem,
        tol_lo=tol_lo,
        tol_hi=tol_hi,
        tol_den=tol_den,
    )
    return f"(=> {active} {relation})"


def _div_freq_relation_expr(
    *,
    freq_in: str,
    freq_out: str,
    ratio: str,
    freq_hw: str,
    rem: str,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> str:
    return (
        f"(and "
        f"(> {freq_hw} 0) "
        f"(>= {rem} 0) "
        f"(< {rem} {ratio}) "
        f"(= {freq_in} (+ (* {freq_hw} {ratio}) {rem})) "
        f"(<= (* {freq_out} {tol_lo}) (* {freq_hw} {tol_den})) "
        f"(>= (* {freq_out} {tol_hi}) (* {freq_hw} {tol_den}))"
        f")"
    )


def _finite_ratio_freq_constraint_expr(
    *,
    active: str,
    freq_in: str,
    freq_out: str,
    ratio_sym: str,
    values: tuple[int, ...],
    freq_hw: str,
    rem: str,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> str:
    arms = [
        "(and "
        f"(= {ratio_sym} {value}) "
        + _div_freq_relation_expr(
            freq_in=freq_in,
            freq_out=freq_out,
            ratio=str(value),
            freq_hw=freq_hw,
            rem=rem,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        )
        + ")"
        for value in values
    ]
    return f"(=> {active} (or {' '.join(arms)}))"


def _smt2_for_diagnosis(smt2_named: str) -> str:
    lines: List[str] = []
    for line in smt2_named.splitlines():
        stripped = line.strip()
        if stripped in _DIAG_SKIP_LINES:
            continue
        if stripped == "(set-logic QF_LIA)":
            lines.append("(set-logic QF_NIA)")
            continue
        lines.append(line)
    return "\n".join(lines) + "\n"


def format_solve_failure_detail(
    tree: Tree,
    *,
    period_tolerance: float,
    smt2_named: str,
    hints: Mapping[str, str],
) -> str:
    unsat_started_at = log_stage_start(
        "diagnose",
        "unsat_core",
        "z3 unsat core",
        hints=len(hints),
    )
    core = format_unsat_diagnosis(smt2_named, hints)
    log_stage_done(
        "diagnose",
        "unsat_core",
        "z3 unsat core",
        unsat_started_at,
        found=bool(core),
    )

    issues_started_at = log_stage_start(
        "diagnose",
        "collect",
        "debug issues",
        nodes=len(tree.nodes),
    )
    issues = collect_debug_issues(tree, period_tolerance)
    log_stage_done(
        "diagnose",
        "collect",
        "debug issues",
        issues_started_at,
        issues=len(issues),
    )

    render_started_at = log_stage_start(
        "diagnose",
        "format",
        "tree graph",
        nodes=len(tree.nodes),
    )
    print_diagnostic_report(tree, issues=issues, unsat_core=core or "")
    log_stage_done(
        "diagnose",
        "format",
        "tree graph",
        render_started_at,
        issues=len(issues),
    )

    summary = format_debug_issues_summary(issues)
    if summary:
        return f"{summary}\n\n完整诊断图已输出到 stderr。"
    if core:
        return "约束冲突；完整诊断图已输出到 stderr。"
    return ""


def format_unsat_diagnosis(
    smt2_named: str,
    hints: Mapping[str, str],
) -> str:
    """用 Z3 从命名约束中提取不可满足核心，生成可读说明。"""
    try:
        from z3 import Solver, unsat
    except ImportError:
        return ""

    solver = Solver()
    try:
        solver.from_string(_smt2_for_diagnosis(smt2_named))
    except Exception:
        return ""
    if solver.check() != unsat:
        return ""

    core = [str(track) for track in solver.unsat_core()]
    if not core:
        return ""

    lines: List[str] = []
    for track in core:
        hint = hints.get(track)
        if hint:
            lines.append(f"- {hint}")
        else:
            lines.append(f"- 约束 {track}")
    return "冲突约束：\n" + "\n".join(lines)


def _raise_solve_failure(
    exc: RuntimeError,
    *,
    tree: Tree,
    period_tolerance: float,
    smt2_named: str,
    hints: Mapping[str, str],
) -> None:
    detail = format_solve_failure_detail(
        tree,
        period_tolerance=period_tolerance,
        smt2_named=smt2_named,
        hints=hints,
    )
    if detail:
        raise RuntimeError(f"{exc}\n\n{detail}") from exc
    raise exc


def build_smt2(
    tree: Tree,
    *,
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    period_tolerance: float,
) -> tuple[str, str, Dict[str, str], List[tuple[str, str, str]]]:
    """编码时钟树约束；返回 consolver SMT、诊断 SMT、说明表与命名约束。"""
    builder = _Smt2Builder()
    node_names = sorted(tree.nodes.keys())
    tol_lo, tol_hi, tol_den = _freq_tolerance_bounds(period_tolerance)
    tol_pct = period_tolerance * 100

    for name in node_names:
        builder.declare(f"(declare-const {_sym(name, 'active')} Bool)")
        builder.declare(f"(declare-const {_sym(name, 'freq')} Int)")
        node = tree.nodes[name]
        if isinstance(node, MuxNode):
            keys = sorted(node.source.keys(), key=lambda k: int(k))
            max_sel = max(int(k) for k in keys)
            builder.declare(f"(declare-const {_sym(name, 'sel')} Int)")
            if node.sel is not None:
                builder.constraint(
                    f"(= {_sym(name, 'sel')} {node.sel})",
                    track=_track("mux", name, "sel", str(node.sel)),
                    hint=f"mux 节点 {name} 固定选择值 {node.sel}",
                )
            else:
                builder.constraint(f"(>= {_sym(name, 'sel')} 0)")
                builder.constraint(f"(<= {_sym(name, 'sel')} {max_sel})")
        if isinstance(node, DivNode) and _div_needs_ratio_var(node):
            builder.declare(f"(declare-const {_sym(name, 'ratio')} Int)")
            if node.ratio is not None:
                builder.constraint(
                    f"(= {_sym(name, 'ratio')} {node.ratio})",
                    track=_track("div", name, "ratio", str(node.ratio)),
                    hint=f"div 节点 {name} 固定分频比 {node.ratio}",
                )
        if isinstance(node, DivNode):
            builder.declare(f"(declare-const {_sym(name, 'freq_hw')} Int)")
            builder.declare(f"(declare-const {_sym(name, 'rem')} Int)")
        if isinstance(node, GateNode):
            builder.declare(f"(declare-const {_sym(name, 'gate_open')} Bool)")
            if node.open is not None:
                lit = "true" if node.open else "false"
                state = "打开" if node.open else "关闭"
                builder.constraint(
                    f"(= {_sym(name, 'gate_open')} {lit})",
                    track=_track("gate", name, "open", lit),
                    hint=f"gate 节点 {name} 固定为{state}",
                )

    for name in node_names:
        node = tree.nodes[name]
        if node.kind == "source":
            if node.freq > 0:
                builder.constraint(
                    _sym(name, "active"),
                    track=_track("source", name, "active"),
                    hint=f"source 节点 {name} 始终有效",
                )
                builder.constraint(
                    f"(= {_sym(name, 'freq')} {node.freq})",
                    track=_track("source", name, "freq", str(node.freq)),
                    hint=f"source 节点 {name} 频率固定为 {node.freq} Hz",
                )
        elif isinstance(node, ClkNode):
            builder.constraint(
                _sym(name, "active"),
                track=_track("clk", name, "active"),
                hint=f"clk 节点 {name} 始终有效",
            )
            if node.freq is not None:
                builder.constraint(
                    f"(= {_sym(name, 'freq')} {node.freq})",
                    track=_track("clk", name, "freq", str(node.freq)),
                    hint=f"clk 节点 {name} 目标频率 {node.freq} Hz",
                )
        elif isinstance(node, PllNode):
            builder.constraint(
                f"(=> {_sym(name, 'active')} (= {_sym(name, 'freq')} {node.freq}))",
                track=_track("pll", name, "freq", str(node.freq)),
                hint=f"pll 节点 {name} 有效时输出频率应为 {node.freq} Hz",
            )

    for name in node_names:
        node = tree.nodes[name]
        if node.kind in ("source", "mux"):
            continue
        parent_name, out_group = parse_source_endpoint(
            node.source, ctx=f"节点 {name!r} source"
        )
        parent = tree.nodes[parent_name]
        act_c = _sym(name, "active")
        act_p = _sym(parent_name, "active")
        freq_c = _sym(name, "freq")
        freq_p = _sym(parent_name, "freq")
        builder.constraint(
            f"(=> {act_c} {act_p})",
            track=_track("route", name, "parent_active", parent_name),
            hint=f"节点 {name} 有效时前级 {parent_name} 必须有效",
        )
        if parent.kind == "mux":
            builder.constraint(
                f"(=> {act_c} (= {freq_c} {freq_p}))",
                track=_track("route", name, "freq_eq", parent_name),
                hint=f"节点 {name} 与前级 mux {parent_name} 同频",
            )
        elif isinstance(parent, DivNode) and parent.div_kind == "cpu_gate":
            if out_group == CPU_GATE_PASS_THROUGH_GROUP:
                pass_parent_name, _ = parse_source_endpoint(
                    parent.source, ctx=f"cpu_gate {parent_name!r} source"
                )
                freq_pass = _sym(pass_parent_name, "freq")
                builder.constraint(
                    f"(=> {act_c} (= {freq_c} {freq_pass}))",
                    track=_track("route", name, "freq_pass", pass_parent_name),
                    hint=(
                        f"节点 {name} 取自 cpu_gate {parent_name}"
                        f"[{CPU_GATE_PASS_THROUGH_GROUP}]，"
                        f"与 {pass_parent_name} 同频"
                    ),
                )
            else:
                builder.constraint(
                    f"(=> {act_c} (= {freq_c} {freq_p}))",
                    track=_track("route", name, "freq_eq", parent_name),
                    hint=f"节点 {name} 与前级 cpu_gate {parent_name} 同频",
                )
        elif node.kind in ("gate", "inv", "cell", "clk"):
            builder.constraint(
                f"(=> {act_c} (= {freq_c} {freq_p}))",
                track=_track("route", name, "freq_eq", parent_name),
                hint=f"节点 {name} 与前级 {parent_name} 同频",
            )
        elif node.kind == "pll":
            pass
        elif isinstance(node, DivNode):
            pass

    for name in node_names:
        node = tree.nodes[name]
        if not isinstance(node, MuxNode):
            continue
        act_m = _sym(name, "active")
        freq_m = _sym(name, "freq")
        sel_m = _sym(name, "sel")
        keys = sorted(node.source.keys(), key=lambda k: int(k))
        peer_names: List[str] = []
        freq_arms: List[Tuple[str, str]] = []
        active_arms: List[str] = []
        for key in keys:
            peer_ref = node.source[key]
            peer_name, _ = parse_source_endpoint(
                peer_ref, ctx=f"mux {name!r}"
            )
            peer_names.append(peer_name)
            cond = f"(= {sel_m} {key})"
            freq_arms.append((cond, _sym(peer_name, "freq")))
            active_arms.append(
                f"(and {cond} {_sym(peer_name, 'active')})"
            )
        default_peer = peer_names[0]
        builder.constraint(
            f"(=> {act_m} (= {freq_m} "
            f"{_ite_chain(freq_arms, _sym(default_peer, 'freq'))}))",
            track=_track("mux", name, "freq_select"),
            hint=f"mux 节点 {name} 输出频率跟随当前选择的前级",
        )
        builder.constraint(
            f"(=> {act_m} (or {' '.join(active_arms)}))",
            track=_track("mux", name, "active_select"),
            hint=f"mux 节点 {name} 所选前级分支必须有效",
        )

    for name in node_names:
        node = tree.nodes[name]
        if not isinstance(node, DivNode):
            continue
        parent_name, _ = parse_source_endpoint(
            node.source, ctx="div"
        )
        act_d = _sym(name, "active")
        freq_d = _sym(name, "freq")
        freq_in = _sym(parent_name, "freq")
        freq_hw = _sym(name, "freq_hw")
        rem = _sym(name, "rem")
        div_freq_hint = (
            f"div 节点 {name}：前级 {parent_name} 频率分频后"
            f"应满足输出频率，容差 {tol_pct:g}%"
        )
        if node.div_kind in ("div", "div_n"):
            ratio = _sym(name, "ratio")
            values = _finite_ratio_values(node)
            if values is None:
                builder.constraint(
                    f"(and (>= {ratio} 1) (<= {ratio} 64))",
                    track=_track("div", name, "ratio_range"),
                    hint=f"div 节点 {name} 分频比范围 1～64",
                )
                builder.constraint(
                    _div_freq_constraint_expr(
                        active=act_d,
                        freq_in=freq_in,
                        freq_out=freq_d,
                        ratio=ratio,
                        freq_hw=freq_hw,
                        rem=rem,
                        tol_lo=tol_lo,
                        tol_hi=tol_hi,
                        tol_den=tol_den,
                    ),
                    track=_track("div", name, "freq_relation"),
                    hint=div_freq_hint,
                )
            else:
                allowed = " ".join(f"(= {ratio} {value})" for value in values)
                builder.constraint(
                    f"(or {allowed})",
                    track=_track("div", name, "ratio_range"),
                    hint=f"div 节点 {name} 分频比范围 1～64",
                )
                builder.constraint(
                    _finite_ratio_freq_constraint_expr(
                        active=act_d,
                        freq_in=freq_in,
                        freq_out=freq_d,
                        ratio_sym=ratio,
                        values=values,
                        freq_hw=freq_hw,
                        rem=rem,
                        tol_lo=tol_lo,
                        tol_hi=tol_hi,
                        tol_den=tol_den,
                    ),
                    track=_track("div", name, "freq_relation"),
                    hint=div_freq_hint,
                )
        elif node.div_kind in ("dto", "dto_n"):
            ratio = _sym(name, "ratio")
            builder.constraint(
                f"(and (>= {ratio} 2) (<= {ratio} {DTO_MAX_RATIO}))",
                track=_track("div", name, "ratio_range"),
                hint=f"dto 节点 {name} 分频比范围 2～{DTO_MAX_RATIO}",
            )
            builder.constraint(
                _div_freq_constraint_expr(
                    active=act_d,
                    freq_in=freq_in,
                    freq_out=freq_d,
                    ratio=ratio,
                    freq_hw=freq_hw,
                    rem=rem,
                    tol_lo=tol_lo,
                    tol_hi=tol_hi,
                    tol_den=tol_den,
                ),
                track=_track("div", name, "freq_relation"),
                hint=div_freq_hint,
            )
        elif node.div_kind == "div_r":
            ratio = node.ratio
            assert ratio is not None
            builder.constraint(
                _div_freq_constraint_expr(
                    active=act_d,
                    freq_in=freq_in,
                    freq_out=freq_d,
                    ratio=str(ratio),
                    freq_hw=freq_hw,
                    rem=rem,
                    tol_lo=tol_lo,
                    tol_hi=tol_hi,
                    tol_den=tol_den,
                ),
                track=_track("div", name, "freq_relation"),
                hint=(
                    f"div_r 节点 {name} 固定分频比 {ratio}，"
                    f"前级频率分频后应满足输出频率，容差 {tol_pct:g}%"
                ),
            )
        elif node.div_kind == "cpu_gate":
            ratio = _sym(name, "ratio")
            values = _finite_ratio_values(node)
            assert values is not None
            ratio_allowed = " ".join(f"(= {ratio} {value})" for value in values)
            builder.constraint(
                f"(or {ratio_allowed})",
                track=_track("div", name, "ratio_range"),
                hint=f"cpu_gate 节点 {name} 分频比只能是 2、3、4、6",
            )
            builder.constraint(
                _finite_ratio_freq_constraint_expr(
                    active=act_d,
                    freq_in=freq_in,
                    freq_out=freq_d,
                    ratio_sym=ratio,
                    values=values,
                    freq_hw=freq_hw,
                    rem=rem,
                    tol_lo=tol_lo,
                    tol_hi=tol_hi,
                    tol_den=tol_den,
                ),
                track=_track("div", name, "freq_relation"),
                hint=div_freq_hint,
            )

    for name in node_names:
        node = tree.nodes[name]
        if isinstance(node, GateNode):
            act_g = _sym(name, "active")
            open_g = _sym(name, "gate_open")
            builder.constraint(
                f"(=> {act_g} {open_g})",
                track=_track("gate", name, "must_open"),
                hint=f"gate 节点 {name} 有效时必须打开",
            )

    for name in node_names:
        act = _sym(name, "active")
        freq = _sym(name, "freq")
        builder.constraint(
            f"(=> {act} (> {freq} 0))",
            track=_track("node", name, "active_positive_freq"),
            hint=f"节点 {name} 有效时频率必须为正",
        )
        builder.constraint(
            f"(=> (not {act}) (= {freq} 0))",
            track=_track("node", name, "inactive_zero_freq"),
            hint=f"节点 {name} 无效时频率为 0",
        )

    _ = pll_sc_fbdiv_min
    _ = pll_sc_fbdiv_max

    plain, named, hints, tracked = builder.finish()
    return plain, named, hints, tracked


def _model_bool(model: Mapping[str, object], sym: str) -> bool:
    val = model.get(sym)
    if val is True:
        return True
    if val is False:
        return False
    if isinstance(val, int):
        return val != 0
    raise ValueError(f"模型变量 {sym!r} 不是布尔值: {val!r}")


def _model_int(model: Mapping[str, object], sym: str) -> int:
    val = model.get(sym)
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, int):
        return val
    if isinstance(val, dict) and "value" in val:
        inner = val["value"]
        if isinstance(inner, int):
            return inner
    raise ValueError(f"模型变量 {sym!r} 不是整数: {val!r}")


def parse_solve_model(
    tree: Tree,
    model: Mapping[str, object],
) -> Tuple[
    Dict[str, bool],
    Dict[str, int],
    Dict[str, int],
    Dict[str, int],
    Dict[str, bool],
]:
    """从 consolver 模型解析 active、freq、ratio、mux_sel、gate_open。"""
    active: Dict[str, bool] = {}
    freq: Dict[str, int] = {}
    ratios: Dict[str, int] = {}
    mux_sel: Dict[str, int] = {}
    gate_open: Dict[str, bool] = {}

    for name, node in tree.nodes.items():
        active[name] = _model_bool(model, _sym(name, "active"))
        freq[name] = _model_int(model, _sym(name, "freq"))
        if isinstance(node, MuxNode):
            mux_sel[name] = (
                node.sel
                if node.sel is not None
                else _model_int(model, _sym(name, "sel"))
            )
        if isinstance(node, DivNode):
            if _div_needs_ratio_var(node):
                ratios[name] = (
                    node.ratio
                    if node.ratio is not None
                    else _model_int(model, _sym(name, "ratio"))
                )
            elif node.div_kind == "div_r" and node.ratio is not None:
                ratios[name] = node.ratio
        if isinstance(node, GateNode):
            gate_open[name] = (
                node.open != 0
                if node.open is not None
                else _model_bool(model, _sym(name, "gate_open"))
            )

    return active, freq, ratios, mux_sel, gate_open


def solve_tree_constraints(
    tree: Tree,
    *,
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    period_tolerance: float,
    timeout_ms: int | None = None,
) -> Tuple[Dict[str, bool], Dict[str, int], Dict[str, int], Dict[str, int], Dict[str, bool]]:
    """生成 SMT、调用 consolver 并解析模型。"""
    build_started_at = log_stage_start(
        "smt",
        "build",
        "tree constraints",
        nodes=len(tree.nodes),
    )
    smt2, smt2_named, hints, tracked = build_smt2(
        tree,
        pll_sc_fbdiv_min=pll_sc_fbdiv_min,
        pll_sc_fbdiv_max=pll_sc_fbdiv_max,
        period_tolerance=period_tolerance,
    )
    log_stage_done(
        "smt",
        "build",
        "tree constraints",
        build_started_at,
        lines=smt2.count("\n"),
        tracked=len(tracked),
    )
    try:
        model = run_consolver_solve(
            smt2,
            label="tree constraints",
            timeout_ms=timeout_ms,
        )
    except RuntimeError as exc:
        _raise_solve_failure(
            exc,
            tree=tree,
            period_tolerance=period_tolerance,
            smt2_named=smt2_named,
            hints=hints,
        )
    parse_started_at = log_stage_start(
        "smt",
        "parse",
        "tree constraints",
        model_items=len(model),
    )
    result = parse_solve_model(tree, model)
    log_stage_done("smt", "parse", "tree constraints", parse_started_at)
    return result
