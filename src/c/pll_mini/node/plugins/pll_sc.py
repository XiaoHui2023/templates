from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .pll import PllNode


class PllScNode(PllNode):
    """Concrete pll_sc node plugin."""

    kind: Literal["pll_sc"] = "pll_sc"
    pll_kind: Literal["sc"] = Field(default="sc", description="Device variant")


class PllScSettings(BaseModel):
    """Plugin-owned configuration defaults."""

    model_config = ConfigDict(extra="forbid")

    pll_sc_fbdiv_min: int = Field(
        16,
        ge=1,
        le=4095,
        description="允许 PLL SC FBDIV 下限。",
    )

    pll_sc_fbdiv_max: int = Field(
        84,
        ge=1,
        le=4095,
        description="允许 PLL SC FBDIV 上限。",
    )

    @model_validator(mode="after")
    def _validate_pll_sc_fbdiv_range(self) -> PllScSettings:
        if self.pll_sc_fbdiv_min > self.pll_sc_fbdiv_max:
            raise ValueError(
                f"pll_sc_fbdiv_min ({self.pll_sc_fbdiv_min}) 须不大于 "
                f"pll_sc_fbdiv_max ({self.pll_sc_fbdiv_max})"
            )
        return self
