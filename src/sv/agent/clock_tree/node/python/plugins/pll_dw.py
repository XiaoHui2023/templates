from __future__ import annotations

from ._families import PllConfig


class PllDwConfig(PllConfig):
    """DW PLL 配置。"""

    register_roles = ("lock", "fbdiv", "prediv", "reset", "pwron", "shift", "bypass", "divvcor", "r", "p", "divvcop", "enr", "enp")
