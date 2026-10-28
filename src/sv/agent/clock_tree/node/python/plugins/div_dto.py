from __future__ import annotations

from pydantic import Field

from ..config import NodePluginSettings
from ._families import DividerConfig


class DivDtoConfig(DividerConfig):
    """DTO 分频器配置。"""

    def register_encoding(self, role: str, access: str) -> str | None:
        """返回 step 或 bypass 的实际写入编码。"""
        ratio = f"{access}._resolved_ratio"
        if role == "step":
            return f"({ratio} == 1 ? 0 : (33554432 / {ratio}))"
        if role == "bypass":
            return f"({ratio} == 1)"
        return None


class DivDtoSettings(NodePluginSettings):
    """DTO 的寄存器与稳定等待设置。"""

    reg_high_means_reset: bool | None = None
    reset_on_config: bool | None = None
    settle_ns: int | None = Field(default=None, ge=0)
    sync_wait_ns: int = Field(default=200, gt=0, description="每次复位或 load 变化后的同步等待时间，ns")
