from __future__ import annotations

from .base import NodeBase


class TransparentNode(NodeBase):
    """提供单输入频率透传行为，供插件复用。"""

    @classmethod
    def terminal_demand_from_config(cls, value) -> bool:
        return cls.frequency_demand_from_config(value)

    def frequency_parent(self, group: str = "") -> str | None:
        """单输入透传节点的活动输入输出等频。"""
        return self.selected_input()

    def add_constraints(self, builder) -> None:
        """约束输出频率等于输入频率。"""
        builder._single_input_equal_constraints(self.name, target=self.is_target)

    def verify(self, tree, model, tolerance: float) -> list:
        """回放单输入频率关系。"""
        from .transparent_replay import verify_node

        return verify_node(self, tree, model, tolerance)
