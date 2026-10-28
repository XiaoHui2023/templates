from __future__ import annotations

from pydantic import Field, model_validator

from schema_error import ERR

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

    @model_validator(mode="after")
    def _stable_requires_enabled(self) -> "ClkConfig":
        """稳定时钟默认开启，拒绝矛盾的显式开关。"""
        if self.stable:
            if self.enabled is None:
                self.enabled = 1
            elif self.enabled <= 0:
                raise ValueError(f"{ERR.field('stable')} 为 true 时 {ERR.field('enabled')} 必须大于 0")
        return self
