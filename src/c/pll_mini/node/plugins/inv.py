from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    Field,
    field_validator,
)

from node.base import _coerce_optional_source_field
from node.behaviors import TransparentNode

from .config_paths import normalize_inv_kind

InvKind = Literal["inv", "inv_mux", "inv_cell"]


class InvNode(TransparentNode):
    kind: Literal["inv"] = "inv"
    inv_kind: InvKind = Field(
        "inv",
        description="反相器型号：inv、inv_mux、inv_cell，大小写不限。",
    )
    source: str = Field("", description="前级引用；省略表示无前级。")
    reg: str = Field(
        "",
        description="反相/直通控制寄存器模型路径；pll_mini 仅接受，不写寄存器。",
    )

    @field_validator("inv_kind", mode="before")
    @classmethod
    def _normalize_inv_kind(cls, value: object) -> str:
        return normalize_inv_kind(value)

    @field_validator("source", mode="before")
    @classmethod
    def _coerce_source(cls, value: Any) -> str:
        return _coerce_optional_source_field(value)
