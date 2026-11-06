from __future__ import annotations

from node.discovery import InputForm
from node.validation import normalized_choice
from pydantic import field_validator

from typing import Literal

from pydantic import Field

from node.ratio import QuotientNode


class DivFixedNode(QuotientNode):
    minimum_ratio = 1
    maximum_ratio = 64
    reg_keys = frozenset(())
    fixed_required = True
    configured_maximum = None
    input_forms = (
        InputForm("div", "div_kind", ("div_r",)),
        InputForm("div_r", defaults=(("div_kind", "div_r"),), target_kind="div"),
    )
    """Concrete div_div_r node plugin."""

    kind: Literal["div_div_r"] = "div_div_r"
    div_kind: Literal["div_r"] = Field(default="div_r", description="Device variant")

    @field_validator("div_kind", mode="before")
    @classmethod
    def _normalize_variant(cls, value):
        return normalized_choice(value, ("div_r",), "div_kind")
