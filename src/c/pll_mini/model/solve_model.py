from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from .freq_graph import Port


@dataclass(frozen=True)
class SolveModel:
    """定向搜索模型解析结果。"""

    active: Dict[str, bool]
    port_freq: Dict[Port, int]
    node_values: Dict[str, dict[str, object]] = field(default_factory=dict)

    def values(self, node_name: str) -> dict[str, object]:
        """返回由该节点插件管理的求解状态。"""
        return self.node_values.setdefault(node_name, {})

    def port_hz(self, port: Port) -> int:
        return self.port_freq.get(port, 0)

    def node_hz(self, node_name: str, *, group: str = "") -> int:
        return self.port_hz(Port(node_name, group))

    def primary_hz(self, node_name: str) -> int:
        for port, hz in self.port_freq.items():
            if port.node == node_name and port.group == "":
                return hz
        for port, hz in self.port_freq.items():
            if port.node == node_name:
                return hz
        return 0
