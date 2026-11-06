from __future__ import annotations

from typing import Any, ClassVar, Dict, Optional

from model.freq_graph import Port, parent_port_for_child
from model.smt import act as _act
from model.smt import freq as _freq
from pydantic import (
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)
from reg_paths import validate_regs_exact

from node.base import NodeBase, _coerce_optional_source_field, _validation_node_name


class QuotientNode(NodeBase):
    minimum_ratio: ClassVar[int]
    maximum_ratio: ClassVar[int]
    configured_maximum: ClassVar[int | None]
    fixed_required: ClassVar[bool] = False
    reg_keys: ClassVar[frozenset[str]] = frozenset()

    constraint_fields = {
        "ratio": ("ratio",),
        "configured_ratio": ("ratio",),
        "freq_div": ("source", "ratio", "settings.period_tolerance"),
        "quotient": ("source", "ratio"),
    }

    plan_priority = 10

    def add_constraints(self, builder) -> None:
        """生成整数分频关系与合法分频范围。"""
        add_node_constraints(builder, self.name, self)

    def read_solution(self, builder, raw, model) -> None:
        """读取求解器选定的分频比。"""
        symbol = builder.variable(self.name, "ratio")
        default = self.ratio or self.minimum_ratio
        model.values(self.name)["ratio"] = (
            raw[symbol] if self.regs else raw.get(symbol, default)
        )

    def resolved_values(self, model) -> dict[str, object]:
        """保留已求解分频比，不替换非法配置值。"""
        ratio = self.ratio or model.values(self.name).get("ratio", 0)
        minimum = self.minimum_ratio
        maximum = self.maximum_ratio
        if (
            type(ratio) is not int
            or ratio < minimum
            or (self.ratio is None and ratio > maximum)
        ):
            raise ValueError(
                f"nodes[{self.name!r}].ratio={ratio!r} 不在合法范围 {minimum}..{maximum}"
            )
        return {"ratio": ratio}

    def static_hz(self, tree, model, group: str, upstream) -> int:
        """按固定或已解分频比回放频率。"""
        ratio = self.ratio or model.values(self.name).get("ratio", 0)
        return upstream(self.source) // ratio if self.source and ratio > 0 else 0

    def verify(self, tree, model, tolerance: float) -> list:
        """检查分频公式及频率容差。"""
        return verify_node(self, tree, model, tolerance)

    source: str = Field("", description="前级引用；省略表示无前级。")

    ratio: Optional[int] = Field(
        None,
        ge=1,
        description="正整数比值；范围由插件声明，固定比值时不写寄存器。",
    )

    regs: Dict[str, str] = Field(
        default_factory=dict,
        description="插件声明的寄存器角色；固定 ratio 时不得配置。",
    )

    @field_validator("source", mode="before")
    @classmethod
    def _coerce_source(cls, value: Any) -> str:
        return _coerce_optional_source_field(value)

    @model_validator(mode="after")
    def _validate_ratio_registers(self, info: ValidationInfo):
        name = _validation_node_name(self, info)
        if self.fixed_required and self.ratio is None:
            raise ValueError(f"nodes[{name!r}].ratio is required")
        if self.ratio is not None:
            if (
                self.configured_maximum is not None
                and self.ratio > self.configured_maximum
            ):
                raise ValueError(
                    f"nodes[{name!r}].ratio must not exceed {self.configured_maximum}"
                )
            if self.regs:
                raise ValueError(f"nodes[{name!r}].regs must be empty with fixed ratio")
        validate_regs_exact(self.regs, self.reg_keys, node_name=name, kind=self.kind)
        return self


def add_node_constraints(builder, name: str, node) -> None:
    act = _act(name)
    ratio = builder.variable(name, "ratio")
    builder._declare(ratio, "Int")
    minimum = node.minimum_ratio
    maximum = node.maximum_ratio
    upper = (
        f"(= {ratio} {node.ratio})"
        if node.ratio is not None
        else f"(<= {ratio} {maximum})"
    )
    builder._add(
        f"{name}__configured_ratio_domain",
        f"(and (>= {ratio} {minimum}) {upper})",
    )
    try:
        parent = parent_port_for_child(builder.tree, name)
    except ValueError:
        builder._add(f"{name}__no_source_inactive", f"(not {act})")
        return
    out = _freq(Port(name, ""))
    builder._add(f"{name}__parent_active", f"(=> {act} {_act(parent.node)})")
    target = node.fixed_hz() or builder.required_freqs.get(Port(name))
    if target is not None and target > 0:
        # Keep the quotient formula for solving/diagnostics; expose its linear bounds.
        low = (target * builder.tol_lo + builder.tol_den - 1) // builder.tol_den
        high = target * builder.tol_hi // builder.tol_den
        builder._add(
            f"{name}__freq_div_interval",
            f"(=> {act} (and (<= (* {low} {ratio}) {_freq(parent)}) "
            f"(< {_freq(parent)} (* {high + 1} {ratio}))))",
        )
    hw = builder.variable(name, "quotient")
    product = f"(* {hw} {ratio})"
    builder._add(
        f"{name}__quotient",
        f"(=> {act} (and (>= {hw} 0) (<= {product} {_freq(parent)}) "
        f"(< {_freq(parent)} (+ {product} {ratio}))))",
    )
    builder._add(
        f"{name}__freq_div",
        (
            f"(=> {act} (and "
            f"(<= (* {out} {builder.tol_lo}) (* {hw} {builder.tol_den})) "
            f"(>= (* {out} {builder.tol_hi}) (* {hw} {builder.tol_den}))"
            f"))"
        ),
    )


def verify_node(node, tree, model, period_tolerance):
    from model.arithmetic import (
        div_hw_from_input,
        freq_tolerance_bounds,
        freq_within_tolerance,
    )
    from model.freq_graph import (
        Port,
        parent_port_for_child,
    )
    from model.verify import VerifyIssue, _hz_mhz, _path_for_node

    issues = []
    tol_lo, tol_hi, tol_den = freq_tolerance_bounds(period_tolerance)
    for name, node in [(node.name, node)]:
        ratio = model.values(name).get("ratio", 0)
        if ratio < 1 or not node.source:
            continue
        parent_port = parent_port_for_child(tree, name)
        f_in = model.port_hz(parent_port)
        f_out = model.port_hz(Port(name, ""))
        if f_in <= 0 or f_out <= 0:
            continue
        try:
            f_hw, rem = div_hw_from_input(f_in, ratio)
        except ValueError:
            issues.append(
                VerifyIssue(
                    headline=f"{node.kind} {name} 分频公式不成立",
                    formula="f_ref = f_hw × ratio + rem，0 ≤ rem < ratio",
                    detail=f"f_ref={_hz_mhz(f_in)}，ratio={ratio}",
                    path_nodes=_path_for_node(tree, name, model),
                )
            )
            continue
        if not freq_within_tolerance(
            f_out, f_hw, tol_lo=tol_lo, tol_hi=tol_hi, tol_den=tol_den
        ):
            issues.append(
                VerifyIssue(
                    headline=f"{node.kind} {name} 输出超出容差",
                    formula=(
                        "f_hw = f_ref // ratio；"
                        f"f_out 在 f_hw 的 ±{period_tolerance * 100:g}% 内"
                    ),
                    detail=(
                        f"f_ref={_hz_mhz(f_in)}，ratio={ratio}，"
                        f"f_hw={_hz_mhz(f_hw)}，rem={rem}，"
                        f"f_out={_hz_mhz(f_out)}"
                    ),
                    path_nodes=_path_for_node(tree, name, model),
                )
            )

    return issues
