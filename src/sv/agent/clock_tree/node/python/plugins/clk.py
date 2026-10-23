from __future__ import annotations

from pydantic import Field

from ..config import NodePluginConfig


class ClkConfig(NodePluginConfig):
    """时钟端点配置。"""

    frequence: int | None = Field(default=None, description="打开时的目标频率，单位为 Hz")
    enabled: int | None = Field(default=None, description="正数打开，零关闭，负数由约束决定")
    low_power: bool | None = Field(default=None, description="低功耗时优先关闭")
    stable: bool | None = Field(default=None, description="标记为稳定时钟")
    check_duty: bool | None = Field(default=None, description="是否检查占空比")
    unfix_frequence: bool | None = Field(default=None, description="解除频率固定约束")
    unfix_enabled: bool | None = Field(default=None, description="解除使能固定约束")
