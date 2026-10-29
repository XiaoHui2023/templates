from __future__ import annotations

from typing import Literal

from pydantic import Field

from .pll import PllNode


class PllInnoNode(PllNode):
    """Concrete pll_inno node plugin."""

    kind: Literal["pll_inno"] = "pll_inno"
    pll_kind: Literal["inno"] = Field(default="inno", description="Device variant")
