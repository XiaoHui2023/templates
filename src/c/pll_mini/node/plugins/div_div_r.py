from __future__ import annotations

from typing import Literal

from pydantic import Field

from .div import DivNode


class DivFixedNode(DivNode):
    """Concrete div_div_r node plugin."""

    kind: Literal["div_div_r"] = "div_div_r"
    div_kind: Literal["div_r"] = Field(default="div_r", description="Device variant")
