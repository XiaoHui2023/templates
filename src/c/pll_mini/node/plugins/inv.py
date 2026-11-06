from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from node.behaviors import RecordedControlNode
from node.validation import normalized_choice


class InvNode(RecordedControlNode):
    kind: Literal["inv"] = "inv"
    inv_kind: Literal["inv"] = Field(default="inv")

    @field_validator("inv_kind", mode="before")
    @classmethod
    def _normalize_variant(cls, value):
        return normalized_choice(value, ("inv",), "inv_kind")
