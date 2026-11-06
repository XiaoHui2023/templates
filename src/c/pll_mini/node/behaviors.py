from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator

from .base import NodeBase, _coerce_optional_source_field, _coerce_required_freq


class TransparentNode(NodeBase):
    """提供单输入频率透传行为，供插件复用。"""

    @classmethod
    def terminal_demand_from_config(cls, value, *, frequency: bool) -> bool:
        return frequency

    def frequency_parent(self, group: str = "") -> str | None:
        """单输入透传节点的活动输入输出等频。"""
        return self.selected_input()

    def add_constraints(self, builder) -> None:
        """约束输出频率等于输入频率。"""
        builder._single_input_equal_constraints(self.name, target=self.is_target)

    def verify(self, tree, model, tolerance: float) -> list:
        """回放单输入频率关系。"""
        from .transparent_replay import verify_node

        return verify_node(self, tree, model, tolerance)


class SingleInputNode(TransparentNode):
    """Transparent frequency behavior with one optional input reference."""

    source: str = Field("", description="前级引用；省略表示无前级。")

    @field_validator("source", mode="before")
    @classmethod
    def _coerce_source(cls, value):
        return _coerce_optional_source_field(value)


class RecordedControlNode(SingleInputNode):
    """A pass-through with accepted, non-programmed control metadata."""

    reg: str = Field("", description="控制寄存器路径；仅记录，不生成写入。")


class FixedFrequencyNode(NodeBase):
    """Origin whose supplied frequency is fixed whenever its output is active."""

    is_anchor = True
    frequency_rule: ClassVar[str]
    freq: int = Field(..., ge=1, description="输入频率，单位 Hz。")

    @field_validator("freq", mode="before")
    @classmethod
    def _coerce_freq(cls, value):
        return _coerce_required_freq(value)

    def add_constraints(self, builder):
        from model.freq_graph import Port
        from model.smt import act, freq

        builder._add(
            self.name + "__" + self.frequency_rule,
            f"(=> {act(self.name)} (= {freq(Port(self.name, ''))} {self.freq}))",
        )
