from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from node.behaviors import FixedFrequencyNode
from node.validation import normalized_choice


class ClockSourceNode(FixedFrequencyNode):
    kind: Literal["source"] = "source"
    source_kind: Literal["source"] = Field(default="source")
    frequency_rule = "source_freq"

    @field_validator("source_kind", mode="before")
    @classmethod
    def _normalize_variant(cls, value):
        return normalized_choice(value, ("source",), "source_kind")
