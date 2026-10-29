from __future__ import annotations

from typing import Literal

from pydantic import Field

from .pll import PllNode


class PllDwNode(PllNode):
    """Concrete pll_dw node plugin."""

    kind: Literal["pll_dw"] = "pll_dw"
    pll_kind: Literal["dw"] = Field(default="dw", description="Device variant")
