from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Union

from model.freq_graph import output_ports, parent_port_for_child
from model.smt import act as _act
from model.smt import freq as _freq
from model.smt import port_suffix as _port_suffix
from pydantic import (
    Field,
    ValidationInfo,
    computed_field,
    field_validator,
    model_validator,
)

from node.base import (
    NodeBase,
    _coerce_optional_source_field,
    _validation_node_name,
)

from .config_paths import (
    INNO_PLL_OUTPUT_GROUPS,
    normalize_pll_kind,
    validate_pll_regs_exact,
)

if TYPE_CHECKING:
    from model.verify import VerifyIssue


PllKind = Literal["tci", "sc", "dw", "inno"]


def _coerce_optional_freq_map(value: Any) -> Optional[Union[int, Dict[str, int]]]:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        return {str(key): int(freq) for key, freq in value.items()}
    return int(value)


class PllNode(NodeBase):
    constraint_fields = {"pll_freq": ("freq",), "fixed_freq": ("freq",)}
    is_anchor = True
    independent_outputs = True
    plan_group = "pll"

    def add_constraints(self, builder) -> None:
        """固定输出端口频率，寄存器系数在求解后计算。"""
        add_node_constraints(builder, self.name, self)

    def fixed_hz(self, group: str = "") -> int | None:
        """返回对应输出组的固定频率。"""
        return self.freq_for_group(group)

    def fit(self, tree, model, settings) -> None:
        """反推当前 PLL 的寄存器系数。"""
        from .pll_fit import fit_node

        fit_node(
            self,
            tree,
            model,
            pll_sc_fbdiv_min=settings.pll_sc_fbdiv_min,
            pll_sc_fbdiv_max=settings.pll_sc_fbdiv_max,
            period_tolerance=settings.period_tolerance,
        )

    def resolved_values(self, model) -> dict[str, object]:
        """将寄存器系数整理为配置值。"""
        from .pll_cfg import pll_cfg_from_solved

        values = model.values(self.name).get("coefficients", {})
        return (
            {
                "pll_cfg": pll_cfg_from_solved(
                    self.pll_kind, values, output_groups=self.output_groups
                )
            }
            if self.regs and values
            else {}
        )

    def verify(self, tree, model, tolerance: float) -> list:
        """按硅片公式回放输出频率。"""
        return verify_node(self, tree, model, tolerance)

    def build_plan_group(self, tree, index, resolved):
        """归并同类 PLL 的配置函数。"""
        from .pll_plan import build_pll_plan

        return build_pll_plan(tree, index, resolved)

    kind: Literal["pll"] = "pll"
    freq: Optional[Union[int, Dict[str, int]]] = Field(
        default=None,
        description=(
            "目标输出频率，单位 Hz；inno 可填写 {'0': hz, '1': hz} 指定各输出端口，"
            "也可填写整数表示所有输出端口使用同一频率。"
        ),
    )
    source: str = Field("", description="参考时钟前级引用；省略表示无前级。")
    pll_kind: PllKind = Field(..., description="PLL 型号：tci、sc、dw、inno。")
    regs: Dict[str, str] = Field(
        default_factory=dict,
        description="非空时键须与 pll_kind 允许集合完全一致。",
    )

    @model_validator(mode="after")
    def _validate_pll_freq(self, info: ValidationInfo) -> PllNode:
        node_name = _validation_node_name(self, info)
        if self.freq is None:
            raise ValueError(f"pll 节点 {node_name!r} 必须填写 freq")
        if isinstance(self.freq, dict):
            if self.pll_kind != "inno":
                raise ValueError(
                    f"pll 节点 {node_name!r} pll_kind 为 {self.pll_kind!r} 时 freq 不可为 dict"
                )
            expected = set(self.output_groups)
            actual = set(self.freq)
            if actual != expected:
                raise ValueError(
                    f"pll 节点 {node_name!r} pll_kind 为 inno 时 freq dict 键必须为 {sorted(expected)!r}"
                )
            for group, freq in self.freq.items():
                if freq < 1:
                    raise ValueError(
                        f"pll 节点 {node_name!r} freq[{group!r}] 必须大于 0"
                    )
        elif self.freq is not None and self.freq < 1:
            raise ValueError(f"pll 节点 {node_name!r} freq 若填写须大于 0")
        return self

    @field_validator("freq", mode="before")
    @classmethod
    def _coerce_pll_freq(cls, value: Any) -> Any:
        return _coerce_optional_freq_map(value)

    @field_validator("source", mode="before")
    @classmethod
    def _coerce_source(cls, value: Any) -> str:
        return _coerce_optional_source_field(value)

    @field_validator("pll_kind", mode="before")
    @classmethod
    def _normalize_pll_kind(cls, value: object) -> str:
        return normalize_pll_kind(value)

    @computed_field(  # type: ignore[prop-decorator]
        description="inno 为 0、1 两路输出名；其它 pll 为空；YAML 不可传入。",
    )
    @property
    def output_groups(self) -> List[str]:
        if self.pll_kind == "inno":
            return list(INNO_PLL_OUTPUT_GROUPS)
        return []

    def freq_for_group(self, group: str) -> Optional[int]:
        if self.freq is None:
            return None
        if isinstance(self.freq, dict):
            return self.freq.get(group)
        return self.freq

    @model_validator(mode="after")
    def _validate_pll_regs(self, info: ValidationInfo) -> PllNode:
        validate_pll_regs_exact(
            self.regs,
            self.pll_kind,
            node_name=_validation_node_name(self, info),
            output_groups=self.output_groups,
        )
        return self


def add_node_constraints(builder, name: str, node) -> None:
    act = _act(name)
    fixed_ports = [
        port
        for port in output_ports(builder.tree, name)
        if node.fixed_hz(port.group) is not None
    ]
    if fixed_ports:
        builder._add(f"{name}__fixed_freq_active", act)
    if node.regs:
        try:
            parent = parent_port_for_child(builder.tree, name)
        except ValueError:
            parent = None
        if parent is not None:
            builder._add(f"{name}__parent_active", f"(=> {act} {_act(parent.node)})")
    if node.freq is not None:
        for port in output_ports(builder.tree, name):
            fixed = node.fixed_hz(port.group)
            if fixed is None:
                continue
            builder._add(
                f"{name}__pll_freq__{_port_suffix(port)}",
                f"(=> {act} (= {_freq(port)} {fixed}))",
            )


def verify_node(node, tree, model, period_tolerance):
    from model.arithmetic import freq_tolerance_bounds, freq_within_tolerance
    from model.freq_graph import (
        Port,
        collect_freq_targets,
        collect_non_frequency_targets,
        output_ports,
        parent_port_for_child,
    )
    from model.freq_graph import (
        static_port_hz as _static_port_hz,
    )
    from model.verify import _path_for_edge

    from node.plugins.pll_math import (
        pll_dw_actual_hz,
        pll_inno_actual_hz,
        pll_sc_actual_hz,
        pll_tci_actual_hz,
    )

    issues = []
    targets = collect_freq_targets(tree)
    frozenset(collect_non_frequency_targets(tree))
    tol_lo, tol_hi, tol_den = freq_tolerance_bounds(period_tolerance)
    for name, node in [(node.name, node)]:
        vars_map = model.values(name).get("coefficients", {})
        if not vars_map:
            continue
        ref_port = parent_port_for_child(tree, name)
        f_ref = model.port_hz(ref_port) or _static_port_hz(tree, model, ref_port)
        kind = node.pll_kind
        if kind == "tci":
            clkf = vars_map.get("clkf", 0)
            f_actual = pll_tci_actual_hz(f_ref, clkf)
            f_out = model.port_hz(Port(name, "")) or node.freq_for_group("") or 0
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
                        path=_path_for_edge(tree, name, targets[0][0], model)
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
            f_out = model.port_hz(Port(name, "")) or node.freq_for_group("") or 0
            if f_out <= 0:
                continue
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
                        path=_path_for_edge(tree, name, targets[0][0], model)
                        if targets
                        else (name,),
                    )
                )
        elif kind == "dw":
            fbdiv = vars_map.get("fbdiv", 0)
            p = vars_map.get("p", 0)
            f_actual = pll_dw_actual_hz(f_ref, fbdiv, p)
            f_out = model.port_hz(Port(name, "")) or node.freq_for_group("") or 0
            if f_out <= 0:
                continue
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
                        path=_path_for_edge(tree, name, targets[0][0], model)
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
                f_actual = pll_inno_actual_hz(f_ref, fbdiv, refdiv, p1, p2)
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
                            path=_path_for_edge(tree, name, targets[0][0], model)
                            if targets
                            else (name,),
                        )
                    )

    return issues


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
    from model.verify import VerifyIssue, _hz_mhz

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
