from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    Field,
    field_validator,
)

from node.base import _coerce_optional_source_field
from node.behaviors import TransparentNode

from .config_paths import normalize_cell_kind


class CellNode(TransparentNode):
    kind: Literal["cell"] = "cell"
    cell_kind: str = Field(
        "cell",
        min_length=1,
        description="配置型号，任意非空字符串；仅作记录，频率行为相同。",
    )
    source: str = Field("", description="前级引用；省略表示无前级。")

    @field_validator("cell_kind", mode="before")
    @classmethod
    def _normalize_cell_kind(cls, value: object) -> str:
        return normalize_cell_kind(value)

    @field_validator("source", mode="before")
    @classmethod
    def _coerce_source(cls, value: Any) -> str:
        return _coerce_optional_source_field(value)
