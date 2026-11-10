from __future__ import annotations

from pydantic import Field

from ..config import NodePluginConfig, NodePluginSettings, require_registers


class MuxSettings(NodePluginSettings):
    """无毛刺切换等待设置。"""

    switch_cycles: int = Field(default=8, ge=1, le=1_000_000, description="切换后等待最慢输入的周期数")
    switch_timeout_ns: int = Field(default=1_000_000, ge=1, le=1_000_000_000, description="单次切换等待预算上限，单位 ns")


class MuxConfig(NodePluginConfig):
    """多路选择器配置。"""

    max_sel: int | None = Field(default=None, ge=0, description="source 键集合的可选选择上限")
    sel: int | None = Field(default=None, ge=0, description="目标输入选择值")
    unfix_sel: bool | None = Field(default=None, description="解除选择值固定约束")

    def binding_assignments(self, registers: dict[str, str]) -> list[tuple[str, str]]:
        """检查可编程选择或固定选择的配置。"""
        values = []
        if registers:
            require_registers(registers, ("reg",))
        else:
            if self.sel is None or self.unfix_sel:
                raise ValueError("缺少 'reg'；固定选择需要填写 'sel'，且不能解除固定")
            values.append(("_hardwired", "1'b1"))
        if self.sel is not None and self.unfix_sel is None:
            values.append(("unfix_sel", "1'b0"))
        return values
