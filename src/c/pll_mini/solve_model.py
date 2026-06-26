from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from freq_model import Port


@dataclass(frozen=True)
class SolveModel:
    """consolver 模型解析结果。"""

    active: Dict[str, bool]
    port_freq: Dict[Port, int]
    ratios: Dict[str, int]
    mux_sel: Dict[str, int]
    gate_open: Dict[str, bool]
    pll_vars: Dict[str, Dict[str, int]] = field(default_factory=dict)

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
