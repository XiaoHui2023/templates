from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from node.behaviors import RecordedControlNode
from node.discovery import InputForm
from node.validation import normalized_choice


class InvMuxNode(RecordedControlNode):
    kind: Literal["inv_mux"] = "inv_mux"
    inv_kind: Literal["inv_mux"] = Field(default="inv_mux")
    input_forms = (InputForm("inv", "inv_kind", ("inv_mux",)),)

    @field_validator("inv_kind", mode="before")
    @classmethod
    def _normalize_variant(cls, value):
        return normalized_choice(value, ("inv_mux",), "inv_kind")
