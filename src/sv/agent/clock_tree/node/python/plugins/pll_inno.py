from __future__ import annotations

from pydantic import Field

from ._families import PllConfig


class PllInnoConfig(PllConfig):
    """INNO PLL 配置。"""

    group_id: str | None = Field(default=None, description="共享配置组标识")
