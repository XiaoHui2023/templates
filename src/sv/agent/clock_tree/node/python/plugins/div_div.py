from __future__ import annotations

from pydantic import Field

from ..config import NodePluginSettings
from ._families import DividerConfig


class DivDivConfig(DividerConfig):
    """整数分频器配置。"""

    def register_encoding(self, role: str, access: str) -> str | None:
        """返回分频字段的 N-1 编码。"""
        return f"({access}._resolved_ratio - 1)" if role == "div" else None


class DivDivSettings(NodePluginSettings):
    """整数分频器的寄存器与稳定等待设置。"""

    reg_high_means_reset: bool | None = None
    reset_on_config: bool | None = None
    settle_ns: int | None = Field(default=None, ge=0)
