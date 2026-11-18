from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, computed_field, model_validator


def sv_value(value: int | str) -> str:
    """将配置常量表示为保留位宽的SV表达式。

    Args:
        value: 数值或SV表达式。
    Returns:
        可直接使用的表达式。
    """
    if isinstance(value, int):
        width = max(64, abs(value).bit_length())
        return f"{'-' if value < 0 else ''}{width}'d{abs(value)}"
    return value


class ConstantField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", description="常量名")
    type: str = Field("int", min_length=1, description="SV常量类型")
    value: StrictInt | str = Field(..., description="常量值或SV表达式")

    @computed_field
    @property
    def value_expr(self) -> str:
        """提供保留位宽的常量表达式。"""
        return sv_value(self.value)


class ScalarMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    encode: str | None = Field(None, min_length=1, description="读取 item 的 SV 表达式")
    decode: str = Field("", description="从 gp 写入 item 的 SV 语句")
    member: str | None = Field(None, min_length=1, description="双向映射的item成员路径")
    constant: StrictInt | str | None = Field(None, description="编码常量值或SV表达式")

    @model_validator(mode="after")
    def _source(self):
        """检查映射来源是否明确。"""
        if self.encode is not None and self.constant is not None:
            raise ValueError("encode and constant are mutually exclusive")
        if self.encode is None and self.constant is None and self.member is None:
            raise ValueError("encode, constant or member is required")
        if self.decode and self.member:
            raise ValueError("decode and member are mutually exclusive")
        return self

    @computed_field
    @property
    def source_expr(self) -> str:
        """提供唯一的编码表达式。"""
        if self.constant is not None:
            return sv_value(self.constant)
        return self.encode if self.encode is not None else f"item.{self.member}"


class LengthMapping(ScalarMapping):
    unit: Literal["bytes", "elements"] = Field("bytes", description="长度表达式的单位")


class PackedField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member: str | None = Field(None, min_length=1, description="字段对应的item成员路径")
    constant: StrictInt | str | None = Field(None, description="字段常量，解码时检查相等")
    lsb: int = Field(..., ge=0, le=65535, description="字段在数据中的最低比特位置")
    width: int = Field(..., ge=1, le=65536, description="字段位数")

    @model_validator(mode="after")
    def _source(self):
        """检查字段来源和可表示范围。"""
        if self.member is None and self.constant is None:
            raise ValueError("field requires member or constant")
        if self.lsb + self.width > 65536:
            raise ValueError("field exceeds 65536 bits")
        if isinstance(self.constant, int) and not 0 <= self.constant < (1 << self.width):
            raise ValueError("field constant exceeds width")
        return self

    @computed_field
    @property
    def source_expr(self) -> str:
        """提供字段编码表达式。"""
        return sv_value(self.constant) if self.constant is not None else f"item.{self.member}"


class BufferMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member: str = Field("data", min_length=1, description="item 中的成员路径")
    kind: Literal["packed", "fixed", "dynamic", "queue"] = Field(
        "queue", description="成员容器类型"
    )
    element_bits: int = Field(8, ge=1, le=65536, description="每个元素的有效位数")
    byte_order: Literal["little", "big"] = Field("little", description="元素内字节顺序")
    count: str | None = Field(None, description="编码元素数表达式，省略时取成员容量")
    decode_count: str | None = Field(None, description="解码元素数表达式，可读取bytes和item")
    encoding: Literal["raw", "bit_enable"] = Field("raw", description="原始字节或每比特扩为00/ff")
    fields: list[PackedField] = Field(default_factory=list, description="结构化比特字段布局")
    pack_body: str | None = Field(None, description="自定义编码函数体，操作 item 与 bytes 并返回成功位")
    unpack_body: str | None = Field(None, description="自定义解码函数体，操作 bytes 与 item 并返回成功位")

    @model_validator(mode="after")
    def _paired_bodies(self):
        """检查自定义转换是否包含两个方向。"""
        if (self.pack_body is None) != (self.unpack_body is None):
            raise ValueError("pack_body and unpack_body must be supplied together")
        if self.fields:
            if self.kind != "packed" or self.pack_body is not None or self.count is not None or self.decode_count is not None:
                raise ValueError("fields requires packed kind without custom bodies or counts")
            occupied = 0
            for field in self.fields:
                mask = ((1 << field.width) - 1) << field.lsb
                if occupied & mask:
                    raise ValueError("packed fields overlap")
                occupied |= mask
        if self.pack_body is not None and (self.count is not None or self.decode_count is not None or self.encoding != "raw"):
            raise ValueError("custom bodies cannot use counts or bit_enable encoding")
        return self

    @computed_field
    @property
    def width(self) -> int:
        """提供数据元素实际布局位宽。"""
        return max(f.lsb + f.width for f in self.fields) if self.fields else self.element_bits

    @computed_field
    @property
    def stride(self) -> int:
        """提供每个元素占用的GP字节数。"""
        return self.width if self.encoding == "bit_enable" else (self.width + 7) // 8

    @computed_field
    @property
    def gap_mask(self) -> str:
        """提供布局中未使用比特的掩码。"""
        used = sum(((1 << f.width) - 1) << f.lsb for f in self.fields)
        return f"{self.width}'h{((1 << self.width) - 1) ^ used:x}"
