from __future__ import annotations

from pydantic import Field

from ..config import NodePluginConfig


class MuxConfig(NodePluginConfig):
    """多路选择器配置。"""

    max_sel: int | None = Field(default=None, ge=0, description="source 键集合的可选选择上限")
    sel: int | None = Field(default=None, ge=0, description="目标输入选择值")
    unfix_sel: bool | None = Field(default=None, description="解除选择值固定约束")
