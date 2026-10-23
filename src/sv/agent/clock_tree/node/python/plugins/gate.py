from __future__ import annotations

from pydantic import Field

from ..config import NodePluginConfig, NodePluginSettings


class GateConfig(NodePluginConfig):
    """门控器配置。"""

    open: int | None = Field(default=None, description="正数打开，零关闭，负数由约束决定")
    unfix_open: bool | None = Field(default=None, description="解除通行状态固定约束")
    fix_open: bool | None = Field(default=None, description="固定为打开状态")
    fix_close: bool | None = Field(default=None, description="固定为关闭状态")


class GateSettings(NodePluginSettings):
    """门控寄存器极性设置。"""

    reg_high_means_open: bool | None = None
