from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from registers import Register


class Models(BaseModel):
    model_config = ConfigDict(extra="ignore")

    class_prefix: str = Field("jtag_ctrl_", pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$", description="类型名前缀")
    ir_width: int = Field(8, ge=1, le=4096, description="IR 最大位数")
    dr_width: int = Field(256, ge=1, le=4096, description="DR 最大位数")
    tck_period_ns: float = Field(100, ge=0.002, allow_inf_nan=False, description="TCK 周期，单位 ns")
    idle_cycles: int = Field(0, ge=0, le=2147483647, description="每次扫描后增加的空闲周期")
    use_trst: bool = Field(True, description="复位时驱动 TRST")
    trst_active_low: bool = Field(True, description="TRST 低电平有效")
    trst_pulse_ns: float = Field(100, ge=0.001, allow_inf_nan=False, description="TRST 有效时间，单位 ns")
    reset_cycles: int = Field(5, ge=5, le=2147483647, description="复位时 TMS 连续为 1 的周期数")
    connect_settle_ns: float = Field(10, ge=0.001, allow_inf_nan=False, description="连线检查的电平稳定时间，单位 ns")
    read_fill: int = Field(0, ge=0, le=1, description="读操作从 TDI 发送的默认电平")
    registers: dict[str, Register] = Field(default_factory=lambda: {"idcode": Register()}, description="寄存器配置，字典键为寄存器名字")

    @computed_field
    @property
    def scan_width(self) -> int:
        """返回 IR 和 DR 共用的数据容量。"""
        return max(self.ir_width, self.dr_width)

    @model_validator(mode="after")
    def check_registers(self) -> "Models":
        """检查寄存器值能否放入所配置的位数。

        Raises:
            ValueError: 名字为空、位数过长或数值超出范围。
        """
        for name, reg in self.registers.items():
            if not name or any(ord(c) < 32 or c in (chr(34), chr(92)) for c in name):
                raise ValueError("寄存器名字不能为空，不能含引号、反斜线或控制字符")
            if reg.instruction.bit_length() > self.ir_width:
                raise ValueError(f"寄存器 {name} 的指令超出 IR 位数")
            if reg.length > self.dr_width:
                raise ValueError(f"寄存器 {name} 的长度超出 DR 位数")
            for field in ("value", "expected", "check_mask"):
                if getattr(reg, field).bit_length() > reg.length:
                    raise ValueError(f"寄存器 {name} 的 {field} 超出长度")
        return self
