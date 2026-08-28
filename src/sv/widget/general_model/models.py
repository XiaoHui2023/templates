from pydantic import BaseModel, ConfigDict, Field


class FunctionOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_twos_complement: bool = Field(
        True, description="补码转换为最大位宽内的符号扩展数值。"
    )
    to_twos_complement: bool = Field(
        True, description="数值转换为指定位宽的补码编码。"
    )
    cut: bool = Field(True, description="按起始位和宽度取连续低位结果。")
    slice: bool = Field(True, description="按最高位和最低位取连续位段。")
    resize: bool = Field(True, description="按输入符号重新编码到输出位宽。")
    pad: bool = Field(True, description="把数据截短或用指定 bit 填充高位。")
    reverse_bits: bool = Field(False, description="反转有效位范围内的 bit 顺序。")


class TransposeOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="提供任意秩张量的轴置换类。")


class Models(BaseModel):
    model_config = ConfigDict(extra="ignore")

    class_prefix: str = Field(
        "compute_",
        min_length=1,
        pattern=r"^[A-Za-z_][A-Za-z0-9_$]*$",
        description="类型名前缀，与固定的计算类后缀拼接。",
    )
    base_class: str = Field(
        "uvm_component",
        pattern=(
            r"^[A-Za-z_][A-Za-z0-9_$]*"
            r"(?:::[A-Za-z_][A-Za-z0-9_$]*)*$"
        ),
        description="计算基类继承的 UVM component 类型。",
    )
    data_width: int = Field(
        1024,
        ge=1,
        description="标量计算使用的最大位宽。",
    )
    functions: FunctionOptions = Field(
        default_factory=FunctionOptions,
        description="标量计算函数的选择项。",
    )
    transpose: TransposeOptions = Field(
        default_factory=TransposeOptions,
        description="张量轴置换类的选择项。",
    )
