from __future__ import annotations

import json
import tempfile
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

from load.regmodel import RegModelIndex
from load.tools import consolver_path, run_consolver_solve
from model.arithmetic import freq_tolerance_bounds

from .freq_graph import Port, output_ports, parse_port_ref
from .nodes import Tree
from .smt import act as _act, freq as _freq, safe_name, symbol
from .solve_model import SolveModel


@dataclass(frozen=True)
class NamedConstraint:
    """一个断言及其配置来源。"""

    name: str
    expr: str
    node: str = ""
    rule: str = ""
    paths: tuple[str, ...] = ()


def solve_tree_with_consolver(
    tree: Tree,
    *,
    period_tolerance: float,
    timeout_ms: int | None = None,
    debug_smt_path: Path | None = None,
    reg_index: RegModelIndex | None = None,
) -> SolveModel:
    """求解插件生成的频率图，并在失败时保存可复现诊断。"""
    builder = _SmtBuilder(
        tree,
        period_tolerance=period_tolerance,
        reg_index=reg_index,
    )
    smt2 = builder.render()
    if debug_smt_path is not None:
        builder.write_debug(debug_smt_path)
    try:
        raw = run_consolver_solve(smt2, timeout_ms=timeout_ms)
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("status") not in {
            "sat",
            "unsat",
            "unknown",
        }:
            raise ValueError(f"invalid solver result: {data!r}")
    except (RuntimeError, OSError, ValueError) as exc:
        path = builder.failure_path(debug_smt_path)
        builder.write_debug(path, {"status": "tool_error", "error": str(exc)})
        raise RuntimeError(
            f"[solve/tool_error] {exc}\nSMT: {path}\n映射: {path.with_suffix('.json')}"
        ) from exc
    status = data["status"]
    if status != "sat":
        from report.constraints import diagnose_constraints

        path = builder.failure_path(debug_smt_path)
        report = diagnose_constraints(builder, data, timeout_ms=timeout_ms)
        builder.write_debug(path, report)
        raise RuntimeError(
            report["message"] + f"\nSMT: {path}\n映射: {path.with_suffix('.json')}"
        )
    raw_model = data.get("model")
    try:
        if not isinstance(raw_model, dict):
            raise ValueError("consolver 输出缺少 model 对象")
        return builder.to_solve_model(raw_model)
    except (TypeError, ValueError) as exc:
        path = builder.failure_path(debug_smt_path)
        builder.write_debug(
            path, {"status": "model_error", "error": str(exc), "solver": data}
        )
        raise RuntimeError(f"[solve/model_error] {exc}\nSMT: {path}") from exc


def build_tree_smt2(
    tree: Tree,
    *,
    period_tolerance: float,
    reg_index: RegModelIndex | None = None,
) -> str:
    """生成与正式求解相同的 SMT-LIB 输入。"""
    return _SmtBuilder(
        tree,
        period_tolerance=period_tolerance,
        reg_index=reg_index,
    ).render()


class _SmtBuilder:
    """调度插件并管理公共符号、来源映射与共享字段。"""

    def __init__(
        self,
        tree: Tree,
        *,
        period_tolerance: float,
        reg_index: RegModelIndex | None,
    ) -> None:
        """绑定图、容差及可选寄存器索引。"""
        self.tree = tree
        self.tol_lo, self.tol_hi, self.tol_den = freq_tolerance_bounds(period_tolerance)
        self.reg_index = reg_index
        self.constraints: list[NamedConstraint] = []
        self.decls: dict[str, str] = {}
        self.controls: list[dict[str, object]] = []
        self.shared_control_nodes: set[str] = set()
        self.current_node = ""
        self._build()

    def render(self, constraints=None) -> str:
        """渲染全部或诊断子集断言，保持声明一致。"""
        selected = self.constraints if constraints is None else constraints
        lines = ["(set-logic ALL)", "(set-option :produce-models true)"]
        lines.extend(
            f"(declare-const {name} {typ})" for name, typ in sorted(self.decls.items())
        )
        lines.extend(
            f"(assert (! {item.expr} :named {item.name}))" for item in selected
        )
        return "\n".join([*lines, "(check-sat)", "(get-model)", ""])

    def failure_path(self, configured: Path | None) -> Path:
        """未配置调试路径时保留独立临时目录。"""
        return (
            configured
            or Path(tempfile.mkdtemp(prefix="pll_mini_debug_")) / "problem.smt2"
        )

    def write_debug(self, path: Path, result=None) -> None:
        """保存完整 SMT、节点配置、约束来源和求解结果。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render(), encoding="utf-8")
        data = {
            "schema": 1,
            "nodes": {
                name: node.model_dump(mode="json")
                for name, node in self.tree.nodes.items()
            },
            "constraints": [asdict(item) for item in self.constraints],
            "controls": self.controls,
            "result": result,
            "replay": [str(consolver_path()), "solve", str(path), "--format", "json"],
            "smt_sha256": hashlib.sha256(self.render().encode("utf-8")).hexdigest(),
        }
        path.with_suffix(".json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def to_solve_model(self, raw: dict[str, object]) -> SolveModel:
        """解码公共变量，并由插件读取自有变量。"""
        model = SolveModel(active={}, port_freq={})
        for name, typ in self.decls.items():
            expected = {"Bool": bool, "Int": int}.get(typ)
            if name in raw and expected is not None and type(raw[name]) is not expected:
                raise ValueError(
                    f"missing/invalid {typ} variable {name}={raw.get(name)!r}"
                )
        for name, node in self.tree.nodes.items():
            active = raw.get(_act(name))
            if type(active) is not bool:
                raise ValueError(
                    f"nodes[{name!r}]: missing/invalid {_act(name)}={active!r}"
                )
            model.active[name] = active
            for port in output_ports(self.tree, name):
                value = raw.get(_freq(port))
                if type(value) is not int or value < 0:
                    raise ValueError(
                        f"nodes[{name!r}]: missing/invalid {_freq(port)}={value!r}"
                    )
                model.port_freq[port] = value
            node.read_solution(self, raw, model)
        return model

    def _build(self) -> None:
        if self.reg_index is not None:
            self._shared_register_constraints(collect_only=True)
        for name in self.tree.nodes:
            self._declare(_act(name), "Bool")
            for port in output_ports(self.tree, name):
                self._declare(_freq(port), "Int")
        for name, node in self.tree.nodes.items():
            self.current_node = name
            self._common_node_constraints(name)
            node.add_constraints(self)
        if self.reg_index is not None:
            self._shared_register_constraints()

    def _common_node_constraints(self, name: str) -> None:
        node = self.tree.nodes[name]
        act = _act(name)
        for port in output_ports(self.tree, name):
            freq = _freq(port)
            suffix = port.group or "out"
            self._add(f"{name}__freq_non_negative__{suffix}", f"(>= {freq} 0)")
            self._add(
                f"{name}__inactive_zero__{suffix}", f"(=> (not {act}) (= {freq} 0))"
            )
            if not (node.independent_outputs and port.group):
                self._add(
                    f"{name}__active_positive__{suffix}", f"(=> {act} (> {freq} 0))"
                )
            elif node.fixed_hz(port.group) is None:
                consumers = self._port_consumer_exprs(port)
                condition = f"(or {' '.join(consumers)})" if consumers else "false"
                self._add(
                    f"{name}__unused_zero__{suffix}",
                    f"(=> (not {condition}) (= {freq} 0))",
                )
            fixed = node.fixed_hz(port.group)
            if fixed is not None:
                self._add(
                    f"{name}__fixed_freq__{suffix}",
                    f"(=> {act} (= {freq} {fixed}))",
                    paths=(f"nodes[{name!r}].freq",),
                )

    def _single_input_equal_constraints(
        self, name: str, *, target: bool = False
    ) -> None:
        act = _act(name)
        raw = self.tree.nodes[name].input_refs().get("")
        if raw:
            parent = parse_port_ref(raw, ctx=f"nodes[{name!r}].source")
            self._add(f"{name}__parent_active", f"(=> {act} {_act(parent.node)})")
            self._add(
                f"{name}__freq_equal_parent",
                f"(=> {act} (= {_freq(Port(name))} {_freq(parent)}))",
            )
        node = self.tree.nodes[name]
        if target and (node.fixed_hz() or 0) > 0:
            self._add(f"{name}__target_active", act)
            self._add(
                f"{name}__target_freq",
                f"(= {_freq(Port(name))} {node.fixed_hz()})",
                paths=(f"nodes[{name!r}].freq",),
            )

    def _declare(self, name: str, typ: str) -> None:
        if name in self.decls and self.decls[name] != typ:
            raise ValueError(f"symbol type collision: {name}")
        self.decls[name] = typ

    def _add(self, rule: str, expr: str, *, paths: tuple[str, ...] = ()) -> None:
        label = f"c{len(self.constraints):06d}"
        node = self.tree.nodes[self.current_node]
        self.constraints.append(
            NamedConstraint(
                label,
                expr,
                self.current_node,
                rule,
                paths or node.constraint_paths(rule),
            )
        )

    def _port_consumer_exprs(self, port: Port) -> list[str]:
        consumers = []
        for name, node in self.tree.nodes.items():
            for key, raw in node.input_refs().items():
                if parse_port_ref(raw, ctx=name) == port:
                    consumers.append(
                        f"(and {_act(name)} {node.input_condition(self, key)})"
                    )
        return consumers

    def variable(self, name: str, role: str, typ: str = "Int") -> str:
        """声明插件自有变量，公共层不解释变量角色。"""
        name = symbol("plugin", role, name)
        self._declare(name, typ)
        return name

    def _shared_register_constraints(self, *, collect_only: bool = False) -> None:
        self.controls.clear()
        by_symbol = {}
        for name, node in self.tree.nodes.items():
            self.current_node = name
            for role, (path, expr) in node.control_encodings(self).items():
                ref = self.reg_index.resolve(path, ctx=f"nodes[{name!r}].regs.{role}")
                key = (
                    ref.reg.path,
                    ref.field.name,
                    ref.effective_lsb,
                    ref.effective_width,
                )
                symbol = "register__" + safe_name(repr(key))
                control = {
                    "node": name,
                    "role": role,
                    "path": path,
                    "symbol": symbol,
                    "encoding": expr,
                }
                self.controls.append(control)
                by_symbol.setdefault(symbol, []).append(control)
        self.shared_control_nodes = {
            item["node"]
            for controls in by_symbol.values()
            if len(controls) > 1
            for item in controls
        }
        if collect_only:
            return
        for symbol, controls in by_symbol.items():
            if len(controls) < 2:
                continue
            self._declare(symbol, "Int")
            for control in controls:
                name, role, expr = control["node"], control["role"], control["encoding"]
                self.current_node = name
                field_path = f"nodes[{name!r}]." + (
                    "reg" if role == "reg" else f"regs.{role}"
                )
                self._add(
                    f"{name}__register_encoding__{role}",
                    f"(= {symbol} {expr})",
                    paths=(field_path,),
                )
