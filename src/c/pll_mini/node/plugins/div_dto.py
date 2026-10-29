from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .div import DivNode


class DivDtoNode(DivNode):
    """Concrete div_dto node plugin."""

    kind: Literal["div_dto"] = "div_dto"
    div_kind: Literal["dto", "dto_n"] = Field(
        default="dto", description="Device variant"
    )


class DtoSettings(BaseModel):
    """Plugin-owned configuration defaults."""

    model_config = ConfigDict(extra="forbid")

    dto_reg_high_means_reset: bool = Field(
        False,
        description="为真时 dto 的 rst 写 1 表示复位；为假时写 0 表示复位。",
    )
