from __future__ import annotations

from typing import Literal

from pydantic import Field

from .pll import PllNode


class PllTciNode(PllNode):
    """Concrete pll_tci node plugin."""

    kind: Literal["pll_tci"] = "pll_tci"
    pll_kind: Literal["tci"] = Field(default="tci", description="Device variant")
