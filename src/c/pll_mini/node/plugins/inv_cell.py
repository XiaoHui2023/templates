from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from node.behaviors import RecordedControlNode
from node.discovery import InputForm
from node.validation import normalized_choice


class InvCellNode(RecordedControlNode):
    kind: Literal["inv_cell"] = "inv_cell"
    inv_kind: Literal["inv_cell"] = Field(default="inv_cell")
    input_forms = (InputForm("inv", "inv_kind", ("inv_cell",)),)

    @field_validator("inv_kind", mode="before")
    @classmethod
    def _normalize_variant(cls, value):
        return normalized_choice(value, ("inv_cell",), "inv_kind")
