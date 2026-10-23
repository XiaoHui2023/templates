from __future__ import annotations

from pydantic import Field

from ..config import NodePluginConfig, NodePluginSettings


class SourceConfig(NodePluginConfig):
    """时钟源的频率配置。"""

    frequence: int | None = Field(default=None, description="输出目标频率，单位为 Hz")


class PllConfig(NodePluginConfig):
    """PLL 的频率与开关配置。"""

    frequence: int | None = Field(default=None, description="输出目标频率，单位为 Hz")
    enabled: int | None = Field(default=None, description="正数打开，零关闭，负数由约束决定")


class PllSettings(NodePluginSettings):
    """全部 PLL 共享的运行时设置。"""

    lock_timeout_us: int | None = Field(default=None, ge=1)


class DividerConfig(NodePluginConfig):
    """分频器的通用配置。"""

    ratio: int | None = Field(default=None, description="目标分频比")
    unfix_ratio: bool | None = Field(default=None, description="解除分频比固定约束")


class DividerSettings(NodePluginSettings):
    """分频器共享的频率检查设置。"""

    freq_tolerance: float | None = Field(default=None, gt=0.0, lt=1.0)


class InverterConfig(NodePluginConfig):
    """反相器的通用配置。"""

    inverted: bool | None = Field(default=None, description="是否输出反相信号")
    fix_inverted: bool | None = Field(default=None, description="固定为反相状态")


class InverterSettings(NodePluginSettings):
    """反相器共享的寄存器极性与等待设置。"""

    reg_high_means_inverted: bool | None = None
    settle_ns: int | None = Field(default=None, ge=0)
