from __future__ import annotations

from pydantic import Field

from ..config import NodePluginConfig, NodePluginSettings


class MuxSettings(NodePluginSettings):
    """无毛刺切换等待设置。"""

    switch_cycles: int = Field(default=8, ge=1, le=1_000_000, description="切换后等待最慢输入的周期数")
    switch_timeout_ns: int = Field(default=1_000_000, ge=1, le=1_000_000_000, description="单次切换等待预算上限，单位 ns")


class MuxConfig(NodePluginConfig):
    """多路选择器配置。"""

    max_sel: int | None = Field(default=None, ge=0, description="source 键集合的可选选择上限")
    sel: int | None = Field(default=None, ge=0, description="目标输入选择值")
    unfix_sel: bool | None = Field(default=None, description="解除选择值固定约束")
