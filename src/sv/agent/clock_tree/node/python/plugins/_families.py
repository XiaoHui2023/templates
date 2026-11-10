from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from ..config import NodePluginConfig, NodePluginSettings, require_registers


class SourceConfig(NodePluginConfig):
    """时钟源的频率配置。"""

    frequence: int | None = Field(default=None, description="输出目标频率，单位为 Hz")


class PllConfig(NodePluginConfig):
    """PLL 的频率与开关配置。"""

    frequence: int | None = Field(default=None, description="输出目标频率，单位为 Hz")
    enabled: int | None = Field(default=None, description="正数打开，零关闭，负数由约束决定")
    register_roles: ClassVar[tuple[str, ...]] = ()

    def binding_assignments(self, registers: dict[str, str]) -> list[tuple[str, str]]:
        """检查完整控制字段或外部固定频率。"""
        if registers:
            require_registers(registers, self.register_roles)
            return []
        if self.enabled != 0 and (self.frequence is None or self.frequence <= 0):
            raise ValueError("缺少 PLL 寄存器；外部固定时钟需要正频率或明确关闭")
        return [("_hardwired", "1'b1")]


class PllSettings(NodePluginSettings):
    """全部 PLL 共享的运行时设置。"""

    lock_timeout_us: int | None = Field(default=None, ge=1)


class DividerConfig(NodePluginConfig):
    """分频器的通用配置。"""

    ratio: int | None = Field(default=None, description="目标分频比")
    unfix_ratio: bool | None = Field(default=None, description="解除分频比固定约束")
    register_roles: ClassVar[tuple[str, ...]] = ()
    optional_register_roles: ClassVar[tuple[str, ...]] = ()

    def binding_assignments(self, registers: dict[str, str]) -> list[tuple[str, str]]:
        """检查可编程分频字段或固定分频比。"""
        values = []
        if registers:
            require_registers(registers, self.register_roles, self.optional_register_roles)
        else:
            if self.ratio is None or self.ratio <= 0 or self.unfix_ratio:
                raise ValueError("缺少分频寄存器；固定分频需要正数 'ratio'，且不能解除固定")
            values.append(("_hardwired", "1'b1"))
        if self.ratio is not None and self.ratio > 0 and self.unfix_ratio is None:
            values.append(("unfix_ratio", "1'b0"))
        return values


class DividerSettings(NodePluginSettings):
    """分频器共享的频率检查设置。"""

    freq_tolerance: float | None = Field(default=None, gt=0.0, lt=1.0)


class InverterConfig(NodePluginConfig):
    """反相器的通用配置。"""

    inverted: bool | None = Field(default=None, description="是否输出反相信号")
    fix_inverted: bool | None = Field(default=None, description="固定为反相状态")

    def binding_assignments(self, registers: dict[str, str]) -> list[tuple[str, str]]:
        """检查可编程极性或固定反相状态。"""
        if registers:
            require_registers(registers, ("reg",))
            return []
        if self.fix_inverted and self.inverted is False:
            raise ValueError("'inverted' 与 'fix_inverted' 冲突")
        return [("_hardwired", "1'b1"), ("_fixed_inverted", "1'b0" if self.inverted is False else "1'b1")]


class InverterSettings(NodePluginSettings):
    """反相器共享的寄存器极性与等待设置。"""

    reg_high_means_inverted: bool | None = None
    settle_ns: int | None = Field(default=None, ge=0)
