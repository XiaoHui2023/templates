from __future__ import annotations

from pydantic import Field

from ..config import NodePluginSettings
from ._families import DividerConfig


class DivDtoConfig(DividerConfig):
    """DTO 分频器配置。"""


class DivDtoSettings(NodePluginSettings):
    """DTO 的寄存器与稳定等待设置。"""

    reg_high_means_reset: bool | None = None
    reset_on_config: bool | None = None
    settle_ns: int | None = Field(default=None, ge=0)
