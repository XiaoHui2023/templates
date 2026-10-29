from __future__ import annotations

from typing import Dict, Literal, Optional

from model.freq_graph import Port, parse_port_ref
from model.smt import act as _act
from model.smt import freq as _freq
from pydantic import (
    Field,
    ValidationInfo,
    computed_field,
    field_validator,
    model_validator,
)
from reg_paths import validate_optional_reg

from node.base import NodeBase, _validation_node_name


class MuxNode(NodeBase):
    constraint_fields = {
        "sel": ("sel", "source"),
        "configured_sel": ("sel", "source"),
        "arm_": ("source", "sel"),
    }
    plan_priority = 30

    @field_validator("source", mode="before")
    @classmethod
    def _normalize_inputs(cls, value):
        """将输入编号统一为非负整数字符串，并拒绝重复编号。"""
        if not isinstance(value, dict):
            return value
        result = {}
        for key, raw in value.items():
            try:
                number = int(key)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"source 输入编号 {key!r} 应为非负整数") from exc
            if number < 0 or str(number) in result:
                raise ValueError(f"source 输入编号 {key!r} 为负数或重复编号")
            result[str(number)] = raw
        return result

    def add_constraints(self, builder) -> None:
        """仅选中输入参与输出频率传播。"""
        add_node_constraints(builder, self.name, self)

    def selected_input(self, model=None) -> str | None:
        """优先使用固定选择，其次读取求解结果。"""
        selected = (
            self.sel
            if self.sel is not None
            else (model.values(self.name).get("sel") if model else None)
        )
        return self.source.get(str(selected)) if selected is not None else None

    def input_condition(self, builder, key: str) -> str:
        """返回该输入被选中的 SMT 条件。"""
        return f"(= {builder.variable(self.name, 'sel')} {int(key)})"

    def read_solution(self, builder, raw, model) -> None:
        """读取输入选择变量。"""
        model.values(self.name)["sel"] = int(
            raw.get(builder.variable(self.name, "sel"), self.sel or 0)
        )

    def control_encodings(self, builder) -> dict[str, tuple[str, str]]:
        """共享选择字段直接使用选择编号编码。"""
        return (
            {"reg": (self.reg, builder.variable(self.name, "sel"))} if self.reg else {}
        )

    def resolved_values(self, model) -> dict[str, object]:
        """无求解约束时选择最小输入编号。"""
        selected = (
            self.sel if self.sel is not None else model.values(self.name).get("sel")
        )
        if str(selected) not in self.source:
            selected = min(map(int, self.source)) if self.source else 0
        return {"mux_sel": selected}

    def plan_patches(self, index, settings, resolved) -> list:
        """生成选择字段。"""
        from .mux_writes import expand_mux_patch

        return [expand_mux_patch(index, self, resolved)] if self.reg else []

    kind: Literal["mux"] = "mux"
    source: Dict[str, str] = Field(
        default_factory=dict,
        description="多路输入：键为输入标签，值为前级引用。",
    )
    sel: Optional[int] = Field(
        None,
        ge=0,
        description="mux 选择值；省略表示由求解器决定；已填写时功能固定，不写 reg。",
    )
    reg: str = Field(
        "",
        description="mux 选择寄存器模型点分路径；空则生成时跳过写寄存器；"
        "sel 已填写时也应为空。",
    )

    @computed_field(  # type: ignore[prop-decorator]
        description="mux 的 source 键最大值；YAML 不可传入。",
    )
    @property
    def mux_max_sel(self) -> int:
        if not self.source:
            return 0
        return max(int(k) for k in self.source.keys())

    @model_validator(mode="after")
    def _validate_mux(self, info: ValidationInfo) -> MuxNode:
        validate_optional_reg(
            self.reg, node_name=_validation_node_name(self, info), kind="mux"
        )
        if self.sel is not None:
            if self.reg:
                raise ValueError(
                    f"mux 节点 {_validation_node_name(self, info)!r} "
                    f"已指定 sel 时 reg 应为空"
                )
            if str(self.sel) not in self.source:
                raise ValueError(
                    f"mux 节点 {_validation_node_name(self, info)!r} "
                    f"sel 为 {self.sel}，source 中没有该输入编号；可用编号 {sorted(self.source)}"
                )
        return self


def add_node_constraints(builder, name: str, node) -> None:
    act = _act(name)
    sel = builder.variable(name, "sel")
    builder._declare(sel, "Int")
    source_by_sel = {int(key): value for key, value in node.source.items()}
    keys = sorted(source_by_sel)
    if name in builder.shared_control_nodes and keys:
        choices = " ".join(f"(= {sel} {key})" for key in keys)
        builder._add(f"{name}__configured_sel_domain", f"(or {choices})")
    if not keys:
        builder._add(f"{name}__no_source_inactive", f"(not {act})")
        return
    if node.sel is not None:
        builder._add(f"{name}__sel_fixed", f"(=> {act} (= {sel} {node.sel}))")
    else:
        choices = " ".join(f"(= {sel} {key})" for key in keys)
        builder._add(f"{name}__sel_inside", f"(=> {act} (or {choices}))")
    for key in keys:
        parent = parse_port_ref(source_by_sel[key], ctx=f"{name}.source[{key}]")
        when = f"(and {act} (= {sel} {key}))"
        builder._add(
            f"{name}__arm_{key}__parent_active", f"(=> {when} {_act(parent.node)})"
        )
        builder._add(
            f"{name}__arm_{key}__freq",
            f"(=> {when} (= {_freq(Port(name, ''))} {_freq(parent)}))",
        )
