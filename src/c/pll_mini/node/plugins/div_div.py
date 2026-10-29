from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .div import DivNode


class DivDivNode(DivNode):
    """Concrete div_div node plugin."""

    kind: Literal["div_div"] = "div_div"
    div_kind: Literal["div", "div_n"] = Field(
        default="div", description="Device variant"
    )


class DivSettings(BaseModel):
    """Plugin-owned configuration defaults."""

    model_config = ConfigDict(extra="forbid")

    div_reg_high_means_reset: bool = Field(
        False,
        description="为真时 div 的 rst 写 1 表示复位；为假时写 0 表示复位。",
    )
