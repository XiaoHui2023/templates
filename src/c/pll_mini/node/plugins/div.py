from __future__ import annotations

from typing import Any, Dict, Literal, Optional

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
from node.plugins.divider_math import DTO_MAX_RATIO

from .config_paths import div_reg_keys_for_kind, normalize_div_kind

DivKind = Literal["div", "div_n", "dto", "dto_n", "div_r"]


class DivNode(NodeBase):
    constraint_fields = {
        "ratio": ("ratio", "div_kind"),
        "configured_ratio": ("ratio", "div_kind"),
        "freq_div": ("source", "ratio", "div_kind", "settings.period_tolerance"),
    }
    plan_priority = 10

    def add_constraints(self, builder) -> None:
        """生成整数分频关系与合法分频范围。"""
        add_node_constraints(builder, self.name, self)

    def read_solution(self, builder, raw, model) -> None:
        """读取求解器选定的分频比。"""
        model.values(self.name)["ratio"] = int(
            raw.get(builder.variable(self.name, "ratio"), self.ratio or 0)
        )

    def control_encodings(self, builder) -> dict[str, tuple[str, str]]:
        """按硬件编码约束共享寄存器字段。"""
        if self.ratio is not None or not self.regs:
            return {}
        ratio = builder.variable(self.name, "ratio")
        dto = self.div_kind in ("dto", "dto_n")
        role = "step" if dto else "div"
        encoded = f"(div {DTO_MAX_RATIO} {ratio})" if dto else f"(- {ratio} 1)"
        return {role: (self.regs[role], encoded)}

    def resolved_values(self, model) -> dict[str, object]:
        """保留已求解分频比，并为无目标路径提供默认值。"""
        ratio = self.ratio or model.values(self.name).get("ratio", 0)
        if ratio <= 0:
            ratio = 2 if self.div_kind in ("dto", "dto_n") else 1
        return {"ratio": ratio}

    def static_hz(self, tree, model, group: str, upstream) -> int:
        """按固定或已解分频比回放频率。"""
        ratio = self.ratio or model.values(self.name).get("ratio", 0)
        return upstream(self.source) // ratio if self.source and ratio > 0 else 0

    def verify(self, tree, model, tolerance: float) -> list:
        """检查分频公式及频率容差。"""
        return verify_node(self, tree, model, tolerance)

    def plan_patches(self, index, settings, resolved) -> list:
        """将分频状态编码成寄存器字段。"""
        from .divider_writes import expand_div_patches

        return expand_div_patches(index, self, settings, resolved) if self.regs else []

    kind: Literal["div"] = "div"
    div_kind: DivKind = Field(
        "div",
        description="分频器型号：div、div_n、dto、dto_n、div_r，大小写不限。",
    )
    source: str = Field("", description="前级引用；省略表示无前级。")
    ratio: Optional[int] = Field(
        None,
        ge=1,
        description="分频比；div_r 必填固定值，大于 0，不受可配置 div 的 64 上限；"
        "其余 div 省略表示由求解器决定；已填写时功能固定，不写 regs，且不大于 64。",
    )
    regs: Dict[str, str] = Field(
        default_factory=dict,
        description="非空时键由 div_kind 决定：div/div_n 为 rst、load、div；"
        "dto/dto_n 为 rst、load、bypass、step；"
        "div_r 不可配置寄存器，应为空；ratio 已填写时也应为空。",
    )

    @field_validator("div_kind", mode="before")
    @classmethod
    def _normalize_div_kind(cls, value: object) -> str:
        return normalize_div_kind(value)

    @field_validator("source", mode="before")
    @classmethod
    def _coerce_source(cls, value: Any) -> str:
        return _coerce_optional_source_field(value)

    @model_validator(mode="after")
    def _validate_div_regs(self, info: ValidationInfo) -> DivNode:
        if self.div_kind == "div_r":
            if self.ratio is None:
                raise ValueError(
                    f"div 节点 {_validation_node_name(self, info)!r} "
                    f"div_kind 为 div_r 时须填写 ratio"
                )
        elif self.ratio is not None:
            if self.ratio > 64:
                raise ValueError(
                    f"div 节点 {_validation_node_name(self, info)!r} "
                    f"div_kind 为 {self.div_kind!r} 时 ratio 应不大于 64，"
                    f"得到 {self.ratio}"
                )
            if self.regs:
                raise ValueError(
                    f"div 节点 {_validation_node_name(self, info)!r} "
                    f"已指定 ratio 时 regs 应为空"
                )
        validate_regs_exact(
            self.regs,
            div_reg_keys_for_kind(self.div_kind),
            node_name=_validation_node_name(self, info),
            kind=f"div({self.div_kind})",
        )
        return self


def add_node_constraints(builder, name: str, node) -> None:
    act = _act(name)
    ratio = builder.variable(name, "ratio")
    builder._declare(ratio, "Int")
    if name in builder.shared_control_nodes:
        minimum = 2 if node.div_kind in ("dto", "dto_n") else 1
        maximum = DTO_MAX_RATIO if node.div_kind in ("dto", "dto_n") else 64
        builder._add(
            f"{name}__configured_ratio_domain",
            f"(and (>= {ratio} {minimum}) (<= {ratio} {maximum}))",
        )
    try:
        parent = parent_port_for_child(builder.tree, name)
    except ValueError:
        builder._add(f"{name}__no_source_inactive", f"(not {act})")
        return
    out = _freq(Port(name, ""))
    builder._add(f"{name}__parent_active", f"(=> {act} {_act(parent.node)})")
    min_ratio = 2 if node.div_kind in ("dto", "dto_n") else 1
    builder._add(f"{name}__ratio_min", f"(=> {act} (>= {ratio} {min_ratio}))")
    if node.ratio is not None:
        builder._add(f"{name}__ratio_fixed", f"(=> {act} (= {ratio} {node.ratio}))")
    elif node.div_kind in ("dto", "dto_n"):
        builder._add(f"{name}__ratio_max", f"(=> {act} (<= {ratio} {DTO_MAX_RATIO}))")
    else:
        builder._add(f"{name}__ratio_max", f"(=> {act} (<= {ratio} 64))")
    hw = f"(div {_freq(parent)} {ratio})"
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
        collect_freq_targets,
        collect_non_frequency_targets,
        parent_port_for_child,
    )
    from model.verify import VerifyIssue, _hz_mhz, _path_for_edge

    issues = []
    targets = collect_freq_targets(tree)
    frozenset(collect_non_frequency_targets(tree))
    tol_lo, tol_hi, tol_den = freq_tolerance_bounds(period_tolerance)
    for name, node in [(node.name, node)]:
        ratio = model.values(name).get("ratio", 0)
        if ratio < 1:
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
                    headline=f"div {name} 分频公式不成立",
                    formula="f_ref = f_hw × ratio + rem，0 ≤ rem < ratio",
                    detail=f"f_ref={_hz_mhz(f_in)}，ratio={ratio}",
                    path_nodes=tuple(_path_for_edge(tree, name, targets[0][0], model))
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
                    path_nodes=tuple(_path_for_edge(tree, name, targets[0][0], model))
                    if targets
                    else (name,),
                )
            )

    return issues
