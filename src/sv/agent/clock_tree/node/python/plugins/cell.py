from __future__ import annotations

from pydantic import Field

from ..config import NodePluginConfig


class CellConfig(NodePluginConfig):
    """直通观测点配置。"""

    cell_kind: str | None = Field(default=None, description="显示用的单元类别")
    frequence: int | None = Field(default=None, description="目标频率，单位为 Hz")
    enabled: int | None = Field(default=None, description="正数打开，零关闭，负数由约束决定")
