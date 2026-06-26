from __future__ import annotations

from typing import Dict, List, Mapping, Tuple

from formulas import (
    DTO_MAX_RATIO,
    DW_FBDIV_MAX,
    DW_FBDIV_MIN,
    INNO_FBDIV_HW_MAX,
    INNO_FBDIV_SCALE,
)
from freq_model import (
    Port,
    backward_required_nodes,
    collect_freq_targets,
    is_cpu_gate_passthrough_group,
    is_mux_exclusive_peer,
    output_ports,
    parent_port_for_child,
    parse_port_ref,
    port_freq_sym,
)
from nodes import (
    ClkNode,
    DivNode,
    GateNode,
    MuxNode,
    PllNode,
    Tree,
)
from reg_paths import INNO_PLL_OUTPUT_GROUPS
from smt_encode import (
    Smt2Builder,
    div_freq_constraint_expr,
    freq_tolerance_bounds,
    ite_chain,
    pll_product_freq_constraint_expr,
    sym,
    track,
)
from solve_model import SolveModel

_DIV_RATIO_KINDS = frozenset({"div", "div_n", "dto", "dto_n", "cpu_gate"})


def _div_needs_ratio_var(node: DivNode) -> bool:
    return node.div_kind in _DIV_RATIO_KINDS


def _finite_ratio_values(node: DivNode) -> tuple[int, ...] | None:
    if node.ratio is not None:
        return (node.ratio,)
    if node.div_kind in ("div", "div_n"):
        return tuple(range(1, 65))
    if node.div_kind == "cpu_gate":
        return (2, 3, 4, 6)
    return None


def _inno_fbdiv_legal_expr(fbdiv: str) -> str:
    banned = " ".join(f"(= {fbdiv} {value})" for value in list(range(8)) + [11])
    return f"(not (or {banned}))"


def build_smt2(
    tree: Tree,
    *,
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    period_tolerance: float,
) -> tuple[str, str, Dict[str, str], List[tuple[str, str, str]]]:
    targets = collect_freq_targets(tree)
    if not targets:
        raise ValueError("须至少有一个带正频率的 clk 节点")

    required = backward_required_nodes(tree, targets)
    builder = Smt2Builder()
    tol_lo, tol_hi, tol_den = freq_tolerance_bounds(period_tolerance)
    tol_pct = period_tolerance * 100

    for name in sorted(tree.nodes.keys()):
        builder.declare(f"(declare-const {sym(name, 'active')} Bool)")
        if name not in required:
            builder.constraint(
                f"(not {sym(name, 'active')})",
                track_id=track("node", name, "not_required"),
                hint=f"节点 {name} 不在任何频率目标路径上，保持无效",
            )
            continue

        for port in output_ports(tree, name):
            builder.declare(f"(declare-const {port_freq_sym(port)} Int)")

        node = tree.nodes[name]
        if isinstance(node, MuxNode):
            keys = sorted(node.source.keys(), key=lambda k: int(k))
            max_sel = max(int(k) for k in keys)
            builder.declare(f"(declare-const {sym(name, 'sel')} Int)")
            if node.sel is not None:
                builder.constraint(
                    f"(= {sym(name, 'sel')} {node.sel})",
                    track_id=track("mux", name, "sel", str(node.sel)),
                    hint=f"mux {name} 固定 sel={node.sel}",
                )
            else:
                builder.constraint(f"(>= {sym(name, 'sel')} 0)")
                builder.constraint(f"(<= {sym(name, 'sel')} {max_sel})")

        if isinstance(node, DivNode) and _div_needs_ratio_var(node):
            builder.declare(f"(declare-const {sym(name, 'ratio')} Int)")
            if node.ratio is not None:
                builder.constraint(
                    f"(= {sym(name, 'ratio')} {node.ratio})",
                    track_id=track("div", name, "ratio", str(node.ratio)),
                    hint=f"div {name} 固定分频比 {node.ratio}",
                )
        if isinstance(node, DivNode):
            builder.declare(f"(declare-const {sym(name, 'freq_hw')} Int)")
            builder.declare(f"(declare-const {sym(name, 'rem')} Int)")

        if isinstance(node, GateNode):
            builder.declare(f"(declare-const {sym(name, 'gate_open')} Bool)")
            if node.open is not None:
                lit = "true" if node.open else "false"
                state = "打开" if node.open else "关闭"
                builder.constraint(
                    f"(= {sym(name, 'gate_open')} {lit})",
                    track_id=track("gate", name, "open", lit),
                    hint=f"gate {name} 固定为{state}",
                )

        if isinstance(node, PllNode):
            _declare_pll_vars(builder, node, pll_sc_fbdiv_min, pll_sc_fbdiv_max)

    for name in sorted(required):
        node = tree.nodes[name]
        act = sym(name, "active")

        if node.kind == "source" and node.freq > 0:
            port = Port(name, "")
            builder.constraint(
                f"(=> {act} (= {port_freq_sym(port)} {node.freq}))",
                track_id=track("source", name, "freq"),
                hint=f"source {name} 有效时 = {node.freq} Hz",
            )
        elif isinstance(node, ClkNode):
            builder.constraint(act)
            port = Port(name, "")
            if node.freq is not None and node.freq > 0:
                builder.constraint(
                    f"(= {port_freq_sym(port)} {node.freq})",
                    track_id=track("clk", name, "freq"),
                    hint=f"clk {name} 目标 {node.freq} Hz",
                )
        elif isinstance(node, PllNode) and node.freq is not None and node.pll_kind != "inno":
            port = Port(name, "")
            builder.constraint(
                f"(=> {act} (= {port_freq_sym(port)} {node.freq}))",
                track_id=track("pll", name, "yaml_freq"),
                hint=f"pll {name} 目标 {node.freq} Hz",
            )
        elif isinstance(node, PllNode) and node.pll_kind == "inno" and node.freq is not None:
            port = Port(name, INNO_PLL_OUTPUT_GROUPS[0])
            builder.constraint(
                f"(=> {act} (= {port_freq_sym(port)} {node.freq}))",
                track_id=track("pll", name, "yaml_freq", "0"),
                hint=f"pll inno {name} 输出[0] 目标 {node.freq} Hz",
            )

    for name in sorted(required):
        node = tree.nodes[name]
        if node.kind in ("source", "mux"):
            continue
        act_c = sym(name, "active")
        parent_port = parent_port_for_child(tree, name)
        act_p = sym(parent_port.node, "active")
        builder.constraint(
            f"(=> {act_c} {act_p})",
            track_id=track("route", name, "parent_active", parent_port.node),
            hint=f"{name} 有效时前级 {parent_port.node} 必须有效",
        )

        if isinstance(node, DivNode):
            continue
        if isinstance(node, PllNode):
            continue

        child_ports = output_ports(tree, name)
        if not child_ports:
            continue
        child_out = port_freq_sym(child_ports[0])
        parent_f = port_freq_sym(parent_port)
        if node.kind in ("gate", "inv", "cell", "clk"):
            builder.constraint(
                f"(=> {act_c} (= {child_out} {parent_f}))",
                track_id=track("route", name, "passthrough"),
                hint=f"{name} 透传前级 {parent_port.node} 频率",
            )

    _encode_mux_nodes(builder, tree, required)
    _encode_div_nodes(builder, tree, required, tol_lo, tol_hi, tol_den, tol_pct)
    _encode_pll_nodes(
        builder,
        tree,
        required,
        tol_lo,
        tol_hi,
        tol_den,
        tol_pct,
        pll_sc_fbdiv_min,
        pll_sc_fbdiv_max,
    )
    _encode_gate_nodes(builder, tree, required)
    _encode_cpu_gate_ports(builder, tree, required, tol_lo, tol_hi, tol_den, tol_pct)
    _encode_leaf_source_active(builder, tree, required)

    for name in sorted(required):
        act = sym(name, "active")
        for port in output_ports(tree, name):
            f_sym = port_freq_sym(port)
            builder.constraint(
                f"(=> {act} (> {f_sym} 0))",
                track_id=track("port", name, port.group or "0", "positive"),
                hint=f"{name} 有效时输出频率为正",
            )
            builder.constraint(
                f"(=> (not {act}) (= {f_sym} 0))",
                track_id=track("port", name, port.group or "0", "zero"),
                hint=f"{name} 无效时输出频率为 0",
            )

    return builder.finish()


def _declare_pll_vars(
    builder: Smt2Builder,
    node: PllNode,
    fbdiv_min: int,
    fbdiv_max: int,
) -> None:
    name = node.name
    kind = node.pll_kind
    if kind == "tci":
        builder.declare(f"(declare-const {sym(name, 'clkf')} Int)")
        builder.declare(f"(declare-const {sym(name, 'freq_hw')} Int)")
        return
    if kind == "sc":
        for suffix in ("fbdiv", "refdiv", "postdiv1", "postdiv2", "product", "freq_hw", "rem"):
            builder.declare(f"(declare-const {sym(name, suffix)} Int)")
        return
    if kind == "dw":
        for suffix in ("fbdiv", "p", "postdiv", "freq_hw", "rem"):
            builder.declare(f"(declare-const {sym(name, suffix)} Int)")
        return
    if kind == "inno":
        builder.declare(f"(declare-const {sym(name, 'fbdiv')} Int)")
        builder.declare(f"(declare-const {sym(name, 'refdiv')} Int)")
        for group_id in node.output_groups:
            for suffix in ("postdiv1", "postdiv2", "product", "freq_hw", "rem"):
                builder.declare(
                    f"(declare-const {sym(name, f'{suffix}_{group_id}')} Int)"
                )


def _encode_mux_nodes(
    builder: Smt2Builder,
    tree: Tree,
    required: set[str],
) -> None:
    for name in sorted(required):
        node = tree.nodes[name]
        if not isinstance(node, MuxNode):
            continue
        act_m = sym(name, "active")
        sel_m = sym(name, "sel")
        out_sym = port_freq_sym(Port(name, ""))
        keys = sorted(node.source.keys(), key=lambda k: int(k))
        freq_arms: List[Tuple[str, str]] = []
        for key in keys:
            peer_port = parse_port_ref(
                node.source[key], ctx=f"mux {name!r}"
            )
            cond = f"(= {sel_m} {key})"
            freq_arms.append((cond, port_freq_sym(peer_port)))
            peer_act = sym(peer_port.node, "active")
            builder.constraint(
                f"(=> (and {act_m} {cond}) {peer_act})",
                track_id=track("mux", name, "arm_active", key),
                hint=f"mux {name} 选 {key} 时前级 {peer_port.node} 有效",
            )
            if node.sel is None and is_mux_exclusive_peer(
                tree, name, peer_port.node
            ):
                builder.constraint(
                    f"(=> (not (and {act_m} {cond})) (not {peer_act}))",
                    track_id=track("mux", name, "arm_off", key),
                    hint=(
                        f"mux {name} 未选 {key} 时"
                        f"独占臂 {peer_port.node} 无效"
                    ),
                )
        default_port = parse_port_ref(
            node.source[keys[0]], ctx=f"mux {name!r}"
        )
        builder.constraint(
            f"(=> {act_m} (= {out_sym} "
            f"{ite_chain(freq_arms, port_freq_sym(default_port))}))",
            track_id=track("mux", name, "freq_select"),
            hint=f"mux {name} 输出频率跟随 sel 所选前级",
        )


def _encode_div_nodes(
    builder: Smt2Builder,
    tree: Tree,
    required: set[str],
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
    tol_pct: float,
) -> None:
    for name in sorted(required):
        node = tree.nodes[name]
        if not isinstance(node, DivNode) or node.div_kind == "cpu_gate":
            continue
        parent_port = parent_port_for_child(tree, name)
        act_d = sym(name, "active")
        freq_in = port_freq_sym(parent_port)
        out_port = Port(name, "")
        freq_out = port_freq_sym(out_port)
        freq_hw = sym(name, "freq_hw")
        rem = sym(name, "rem")
        hint = (
            f"div {name}：f_out 由 f_ref/ratio 整除分频，"
            f"容差 {tol_pct:g}%"
        )
        if node.div_kind in ("div", "div_n"):
            ratio_sym = sym(name, "ratio")
            values = _finite_ratio_values(node)
            if values is None:
                builder.constraint(f"(and (>= {ratio_sym} 1) (<= {ratio_sym} 64))")
            else:
                allowed = " ".join(f"(= {ratio_sym} {v})" for v in values)
                builder.constraint(f"(or {allowed})")
            builder.constraint(
                div_freq_constraint_expr(
                    active=act_d,
                    freq_in=freq_in,
                    freq_out=freq_out,
                    ratio=ratio_sym,
                    freq_hw=freq_hw,
                    rem=rem,
                    tol_lo=tol_lo,
                    tol_hi=tol_hi,
                    tol_den=tol_den,
                ),
                track_id=track("div", name, "freq"),
                hint=hint,
            )
        elif node.div_kind in ("dto", "dto_n"):
            ratio_sym = sym(name, "ratio")
            builder.constraint(
                f"(and (>= {ratio_sym} 2) (<= {ratio_sym} {DTO_MAX_RATIO}))"
            )
            builder.constraint(
                div_freq_constraint_expr(
                    active=act_d,
                    freq_in=freq_in,
                    freq_out=freq_out,
                    ratio=ratio_sym,
                    freq_hw=freq_hw,
                    rem=rem,
                    tol_lo=tol_lo,
                    tol_hi=tol_hi,
                    tol_den=tol_den,
                ),
                track_id=track("div", name, "freq"),
                hint=hint,
            )
        elif node.div_kind == "div_r":
            ratio = node.ratio
            assert ratio is not None
            builder.constraint(
                div_freq_constraint_expr(
                    active=act_d,
                    freq_in=freq_in,
                    freq_out=freq_out,
                    ratio=str(ratio),
                    freq_hw=freq_hw,
                    rem=rem,
                    tol_lo=tol_lo,
                    tol_hi=tol_hi,
                    tol_den=tol_den,
                ),
                track_id=track("div", name, "freq"),
                hint=f"div_r {name} 固定 ratio={ratio}，容差 {tol_pct:g}%",
            )


def _encode_cpu_gate_ports(
    builder: Smt2Builder,
    tree: Tree,
    required: set[str],
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
    tol_pct: float,
) -> None:
    for name in sorted(required):
        node = tree.nodes[name]
        if not isinstance(node, DivNode) or node.div_kind != "cpu_gate":
            continue
        parent_port = parent_port_for_child(tree, name)
        act_d = sym(name, "active")
        freq_in = port_freq_sym(parent_port)
        ratio_sym = sym(name, "ratio")
        values = _finite_ratio_values(node)
        assert values is not None
        allowed = " ".join(f"(= {ratio_sym} {v})" for v in values)
        builder.constraint(f"(or {allowed})")
        freq_hw = sym(name, "freq_hw")
        rem = sym(name, "rem")
        for port in output_ports(tree, name):
            freq_out = port_freq_sym(port)
            if is_cpu_gate_passthrough_group(port.group):
                builder.constraint(
                    f"(=> {act_d} (= {freq_out} {freq_in}))",
                    track_id=track("cpu_gate", name, port.group, "pass"),
                    hint=f"cpu_gate {name}[{port.group}] 与前级同频",
                )
            else:
                builder.constraint(
                    div_freq_constraint_expr(
                        active=act_d,
                        freq_in=freq_in,
                        freq_out=freq_out,
                        ratio=ratio_sym,
                        freq_hw=freq_hw,
                        rem=rem,
                        tol_lo=tol_lo,
                        tol_hi=tol_hi,
                        tol_den=tol_den,
                    ),
                    track_id=track("cpu_gate", name, port.group, "div"),
                    hint=(
                        f"cpu_gate {name}[{port.group}] 分频，"
                        f"容差 {tol_pct:g}%"
                    ),
                )


def _encode_pll_nodes(
    builder: Smt2Builder,
    tree: Tree,
    required: set[str],
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
    tol_pct: float,
    fbdiv_min: int,
    fbdiv_max: int,
) -> None:
    for name in sorted(required):
        node = tree.nodes[name]
        if not isinstance(node, PllNode):
            continue
        act = sym(name, "active")
        ref_port = parent_port_for_child(tree, name)
        freq_ref = port_freq_sym(ref_port)
        kind = node.pll_kind

        if kind == "tci":
            clkf = sym(name, "clkf")
            out_sym = port_freq_sym(Port(name, ""))
            builder.constraint(f"(=> {act} (>= {clkf} 1))")
            builder.constraint(
                f"(=> {act} (= {out_sym} (* {freq_ref} {clkf})))",
                track_id=track("pll", name, "tci"),
                hint=f"pll tci {name}：f_out = f_ref × clkf",
            )
        elif kind == "sc":
            fbdiv = sym(name, "fbdiv")
            refdiv = sym(name, "refdiv")
            p1 = sym(name, "postdiv1")
            p2 = sym(name, "postdiv2")
            product = sym(name, "product")
            freq_hw = sym(name, "freq_hw")
            rem = sym(name, "rem")
            out_sym = port_freq_sym(Port(name, ""))
            builder.constraint(
                f"(and (>= {fbdiv} {fbdiv_min}) (<= {fbdiv} {fbdiv_max}))"
            )
            builder.constraint(f"(and (>= {refdiv} 1) (<= {refdiv} 63))")
            builder.constraint(f"(and (>= {p1} 1) (<= {p1} 7))")
            builder.constraint(f"(and (>= {p2} 1) (<= {p2} 7))")
            builder.constraint(
                f"(= {product} (* {refdiv} (* {p1} {p2})))"
            )
            builder.constraint(
                pll_product_freq_constraint_expr(
                    active=act,
                    freq_ref=freq_ref,
                    freq_out=out_sym,
                    fbdiv=fbdiv,
                    product=product,
                    freq_hw=freq_hw,
                    rem=rem,
                    tol_lo=tol_lo,
                    tol_hi=tol_hi,
                    tol_den=tol_den,
                ),
                track_id=track("pll", name, "sc"),
                hint=(
                    f"pll sc {name}：f_out ≈ f_ref×fbdiv/(refdiv×postdiv1×postdiv2)，"
                    f"容差 {tol_pct:g}%"
                ),
            )
        elif kind == "dw":
            fbdiv = sym(name, "fbdiv")
            p = sym(name, "p")
            postdiv = sym(name, "postdiv")
            freq_hw = sym(name, "freq_hw")
            rem = sym(name, "rem")
            out_sym = port_freq_sym(Port(name, ""))
            builder.constraint(
                f"(and (>= {fbdiv} {DW_FBDIV_MIN}) (<= {fbdiv} {DW_FBDIV_MAX}))"
            )
            builder.constraint(f"(and (>= {p} 0) (<= {p} 7))")
            builder.constraint(f"(= {postdiv} (+ {p} 1))")
            builder.constraint(
                pll_product_freq_constraint_expr(
                    active=act,
                    freq_ref=freq_ref,
                    freq_out=out_sym,
                    fbdiv=fbdiv,
                    product=postdiv,
                    freq_hw=freq_hw,
                    rem=rem,
                    tol_lo=tol_lo,
                    tol_hi=tol_hi,
                    tol_den=tol_den,
                ),
                track_id=track("pll", name, "dw"),
                hint=f"pll dw {name}：f_out ≈ f_ref×fbdiv/(p+1)，容差 {tol_pct:g}%",
            )
        elif kind == "inno":
            fbdiv = sym(name, "fbdiv")
            refdiv = sym(name, "refdiv")
            builder.constraint(f"(and (>= {refdiv} 1) (<= {refdiv} 63))")
            builder.constraint(f"(and (>= {fbdiv} 1) (<= {fbdiv} {INNO_FBDIV_HW_MAX}))")
            builder.constraint(_inno_fbdiv_legal_expr(fbdiv))
            for group_id in node.output_groups:
                p1 = sym(name, f"postdiv1_{group_id}")
                p2 = sym(name, f"postdiv2_{group_id}")
                product = sym(name, f"product_{group_id}")
                freq_hw = sym(name, f"freq_hw_{group_id}")
                rem = sym(name, f"rem_{group_id}")
                out_sym = port_freq_sym(Port(name, group_id))
                builder.constraint(f"(and (>= {p1} 1) (<= {p1} 7))")
                builder.constraint(f"(and (>= {p2} 1) (<= {p2} 7))")
                scale = INNO_FBDIV_SCALE
                builder.constraint(
                    f"(= {product} (* {scale} (* {refdiv} (* {p1} {p2}))))"
                )
                builder.constraint(
                    pll_product_freq_constraint_expr(
                        active=act,
                        freq_ref=freq_ref,
                        freq_out=out_sym,
                        fbdiv=fbdiv,
                        product=product,
                        freq_hw=freq_hw,
                        rem=rem,
                        tol_lo=tol_lo,
                        tol_hi=tol_hi,
                        tol_den=tol_den,
                    ),
                    track_id=track("pll", name, "inno", group_id),
                    hint=(
                        f"pll inno {name}[{group_id}]："
                        f"f_out ≈ f_ref×fbdiv/(4×refdiv×postdiv1×postdiv2)，"
                        f"容差 {tol_pct:g}%"
                    ),
                )


def _encode_leaf_source_active(
    builder: Smt2Builder,
    tree: Tree,
    required: set[str],
) -> None:
    from freq_model import _downstream_children

    for name in sorted(required):
        if tree.nodes[name].kind != "source":
            continue
        children = _downstream_children(tree, name)
        if len(children) != 1:
            continue
        act = sym(name, "active")
        child_act = sym(children[0], "active")
        builder.constraint(
            f"(= {act} {child_act})",
            track_id=track("source", name, "follow_child"),
            hint=f"source {name} 仅驱动 {children[0]}，有效性一致",
        )


def _encode_gate_nodes(
    builder: Smt2Builder,
    tree: Tree,
    required: set[str],
) -> None:
    for name in sorted(required):
        node = tree.nodes[name]
        if not isinstance(node, GateNode):
            continue
        builder.constraint(
            f"(=> {sym(name, 'active')} {sym(name, 'gate_open')})",
            track_id=track("gate", name, "must_open"),
            hint=f"gate {name} 有效时必须打开",
        )


def _model_bool(model: Mapping[str, object], sym_name: str) -> bool:
    val = model.get(sym_name)
    if val is True:
        return True
    if val is False:
        return False
    if isinstance(val, int):
        return val != 0
    raise ValueError(f"模型变量 {sym_name!r} 不是布尔值: {val!r}")


def _model_int(model: Mapping[str, object], sym_name: str) -> int:
    val = model.get(sym_name)
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, int):
        return val
    if isinstance(val, dict) and "value" in val:
        inner = val["value"]
        if isinstance(inner, int):
            return inner
    raise ValueError(f"模型变量 {sym_name!r} 不是整数: {val!r}")


def _extract_pll_vars(node: PllNode, model: Mapping[str, object]) -> dict[str, int]:
    name = node.name
    kind = node.pll_kind
    if kind == "tci":
        return {"clkf": _model_int(model, sym(name, "clkf"))}
    if kind == "sc":
        return {
            "fbdiv": _model_int(model, sym(name, "fbdiv")),
            "refdiv": _model_int(model, sym(name, "refdiv")),
            "postdiv1": _model_int(model, sym(name, "postdiv1")),
            "postdiv2": _model_int(model, sym(name, "postdiv2")),
        }
    if kind == "dw":
        return {
            "fbdiv": _model_int(model, sym(name, "fbdiv")),
            "p": _model_int(model, sym(name, "p")),
        }
    if kind == "inno":
        out: dict[str, int] = {
            "fbdiv": _model_int(model, sym(name, "fbdiv")),
            "refdiv": _model_int(model, sym(name, "refdiv")),
        }
        for group_id in node.output_groups:
            out[f"postdiv1_{group_id}"] = _model_int(
                model, sym(name, f"postdiv1_{group_id}")
            )
            out[f"postdiv2_{group_id}"] = _model_int(
                model, sym(name, f"postdiv2_{group_id}")
            )
        return out
    raise ValueError(f"未知 pll_kind {kind!r}")


def parse_solve_model(tree: Tree, model: Mapping[str, object]) -> SolveModel:
    active: Dict[str, bool] = {}
    port_freq: Dict[Port, int] = {}
    ratios: Dict[str, int] = {}
    mux_sel: Dict[str, int] = {}
    gate_open: Dict[str, bool] = {}
    pll_vars: Dict[str, Dict[str, int]] = {}

    for name, node in tree.nodes.items():
        active[name] = _model_bool(model, sym(name, "active"))
        if not active[name]:
            continue
        for port in output_ports(tree, name):
            port_freq[port] = _model_int(model, port_freq_sym(port))
        if isinstance(node, MuxNode):
            mux_sel[name] = (
                node.sel
                if node.sel is not None
                else _model_int(model, sym(name, "sel"))
            )
        if isinstance(node, DivNode):
            if _div_needs_ratio_var(node):
                ratios[name] = (
                    node.ratio
                    if node.ratio is not None
                    else _model_int(model, sym(name, "ratio"))
                )
            elif node.div_kind == "div_r" and node.ratio is not None:
                ratios[name] = node.ratio
        if isinstance(node, GateNode):
            gate_open[name] = (
                node.open != 0
                if node.open is not None
                else _model_bool(model, sym(name, "gate_open"))
            )
        if isinstance(node, PllNode):
            pll_vars[name] = _extract_pll_vars(node, model)

    return SolveModel(
        active=active,
        port_freq=port_freq,
        ratios=ratios,
        mux_sel=mux_sel,
        gate_open=gate_open,
        pll_vars=pll_vars,
    )


_DIAG_SKIP_LINES = frozenset({"(check-sat)", "(get-model)"})


def _smt2_for_diagnosis(smt2_named: str) -> str:
    lines: List[str] = []
    for line in smt2_named.splitlines():
        stripped = line.strip()
        if stripped in _DIAG_SKIP_LINES:
            continue
        lines.append(line)
    return "\n".join(lines) + "\n"


def format_unsat_diagnosis(
    smt2_named: str,
    hints: Mapping[str, str],
) -> str:
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

    core = [str(track_id) for track_id in solver.unsat_core()]
    if not core:
        return ""

    lines: List[str] = []
    for track_id in core:
        hint = hints.get(track_id)
        if hint:
            lines.append(f"- {hint}")
        else:
            lines.append(f"- 约束 {track_id}")
    return "冲突约束：\n" + "\n".join(lines)


def solve_tree_constraints(
    tree: Tree,
    *,
    pll_sc_fbdiv_min: int,
    pll_sc_fbdiv_max: int,
    period_tolerance: float,
    timeout_ms: int | None = None,
) -> SolveModel:
    from diagnose import format_solve_failure_detail
    from tools import log_stage_done, log_stage_start, run_consolver_solve

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
        detail = format_solve_failure_detail(
            tree,
            period_tolerance=period_tolerance,
            smt2_named=smt2_named,
            hints=hints,
        )
        if detail:
            raise RuntimeError(f"{exc}\n\n{detail}") from exc
        raise
    parse_started_at = log_stage_start(
        "smt",
        "parse",
        "tree constraints",
        model_items=len(model),
    )
    result = parse_solve_model(tree, model)
    log_stage_done("smt", "parse", "tree constraints", parse_started_at)
    return result
