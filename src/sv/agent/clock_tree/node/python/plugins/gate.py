from __future__ import annotations

from pydantic import Field

from ..config import NodePluginConfig, NodePluginSettings, require_registers


class GateConfig(NodePluginConfig):
    """门控器配置。"""

    open: int | None = Field(default=None, description="正数打开，零关闭，负数由约束决定")
    unfix_open: bool | None = Field(default=None, description="解除通行状态固定约束")
    fix_open: bool | None = Field(default=None, description="固定为打开状态")
    fix_close: bool | None = Field(default=None, description="固定为关闭状态")

    def binding_assignments(self, registers: dict[str, str]) -> list[tuple[str, str]]:
        """检查门控寄存器或固定电平。"""
        values = []
        if registers:
            require_registers(registers, ("reg",))
        else:
            fixed = 1 if self.fix_open else 0 if self.fix_close else self.open
            if fixed not in (0, 1) or self.unfix_open or (self.fix_open and self.fix_close):
                raise ValueError("缺少 'reg'；固定门控需要明确的 'open' 值，且不能解除固定")
            if self.open in (0, 1) and self.open != fixed:
                raise ValueError("'open' 与固定门控状态冲突")
            values.extend((("_hardwired", "1'b1"), ("open", str(fixed))))
        if self.open in (0, 1) and self.unfix_open is None:
            values.append(("unfix_open", "1'b0"))
        return values


class GateSettings(NodePluginSettings):
    """门控寄存器极性设置。"""

    reg_high_means_open: bool | None = None
