from __future__ import annotations

from typing import Any, Literal

from model.freq_graph import Port
from model.smt import act as _act
from model.smt import freq as _freq
from pydantic import (
    Field,
    field_validator,
    model_validator,
)

from node.base import NodeBase, _coerce_required_freq

from .config_paths import normalize_source_kind

SourceKind = Literal["source", "pad"]


class ClockSourceNode(NodeBase):
    is_anchor = True

    def add_constraints(self, builder) -> None:
        """提供固定输入频率。"""
        add_node_constraints(builder, self.name)

    kind: Literal["source"] = "source"
    source_kind: SourceKind = Field(
        "source",
        description="输入源型号：source、pad，大小写不限。",
    )
    freq: int = Field(
        ...,
        ge=1,
        description="输入源频率，单位 Hz；source、pad 必须填写。",
    )

    @field_validator("source_kind", mode="before")
    @classmethod
    def _normalize_source_kind(cls, value: object) -> str:
        return normalize_source_kind(value)

    @field_validator("freq", mode="before")
    @classmethod
    def _coerce_freq(cls, value: Any) -> Any:
        return _coerce_required_freq(value)

    @model_validator(mode="after")
    def _validate_source_freq(self) -> ClockSourceNode:
        if self.freq < 1:
            raise ValueError("source_kind 为 source、pad 时必须填写大于 0 的 freq")
        return self


def add_node_constraints(builder, name: str) -> None:
    node = builder.tree.nodes[name]
    fixed = getattr(node, "freq", None)
    if fixed is not None:
        builder._add(
            name + "__source_freq",
            f"(=> {_act(name)} (= {_freq(Port(name, ''))} {fixed}))",
        )
