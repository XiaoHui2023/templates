from __future__ import annotations

from ._families import PllConfig


class PllTciConfig(PllConfig):
    """TCI PLL 配置。"""

    register_roles = ("lock", "bypass", "pwrdn", "reset", "clkod", "clkf", "clkr", "bwadj")
