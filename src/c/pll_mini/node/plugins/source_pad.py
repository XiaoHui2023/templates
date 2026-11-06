from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from node.behaviors import FixedFrequencyNode
from node.discovery import InputForm
from node.validation import normalized_choice


class PadNode(FixedFrequencyNode):
    kind: Literal["source_pad"] = "source_pad"
    source_kind: Literal["pad"] = Field(default="pad")
    input_forms = (InputForm("source", "source_kind", ("pad",)),)
    frequency_rule = "source_freq"

    @field_validator("source_kind", mode="before")
    @classmethod
    def _normalize_variant(cls, value):
        return normalized_choice(value, ("pad",), "source_kind")
