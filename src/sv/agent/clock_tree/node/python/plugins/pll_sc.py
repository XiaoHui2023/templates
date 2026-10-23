from __future__ import annotations

from pydantic import Field, model_validator

from ..config import NodePluginSettings
from ._families import PllConfig


class PllScConfig(PllConfig):
    """SC PLL 配置。"""


class PllScSettings(NodePluginSettings):
    """SC PLL 搜索边界。"""

    fbdiv_min: int | None = Field(default=None, ge=1, le=4095)
    fbdiv_max: int | None = Field(default=None, ge=1, le=4095)
    pfd_min_hz: int | None = Field(default=None, ge=1)
    vco_min_hz: int | None = Field(default=None, ge=1)
    vco_max_hz: int | None = Field(default=None, ge=1)
    freq_tolerance: float | None = Field(default=None, gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def _ranges_are_ordered(self) -> "PllScSettings":
        if self.fbdiv_min is not None and self.fbdiv_max is not None and self.fbdiv_min > self.fbdiv_max:
            raise ValueError("fbdiv_min 不得大于 fbdiv_max")
        if self.vco_min_hz is not None and self.vco_max_hz is not None and self.vco_min_hz > self.vco_max_hz:
            raise ValueError("vco_min_hz 不得大于 vco_max_hz")
        return self
