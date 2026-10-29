from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)
from reg_paths import validate_optional_reg

from node.base import _coerce_optional_source_field, _validation_node_name
from node.behaviors import TransparentNode


class GateNode(TransparentNode):
    plan_priority = 20

    def resolved_values(self, model) -> dict[str, object]:
        """配置阶段将门控设为打开。"""
        return {"gate_open": True}

    def plan_patches(self, index, settings, resolved) -> list:
        """生成门控字段。"""
        from .gate_writes import expand_gate_patch

        return [expand_gate_patch(index, self, settings)] if self.reg else []

    kind: Literal["gate"] = "gate"
    source: str = Field("", description="前级引用；省略表示无前级。")
    reg: str = Field(
        "",
        description="门控寄存器模型点分路径；空则不生成寄存器写入。门控固定开启。",
    )

    @field_validator("source", mode="before")
    @classmethod
    def _coerce_source(cls, value: Any) -> str:
        return _coerce_optional_source_field(value)

    @model_validator(mode="after")
    def _validate_gate_reg(self, info: ValidationInfo) -> GateNode:
        validate_optional_reg(
            self.reg, node_name=_validation_node_name(self, info), kind="gate"
        )
        return self


class GateSettings(BaseModel):
    """Plugin-owned configuration defaults."""

    model_config = ConfigDict(extra="forbid")

    gate_reg_high_means_open: bool = Field(
        False,
        description="为真时门控寄存器写 1 表示打开；为假时写 1 表示关闭。",
    )
