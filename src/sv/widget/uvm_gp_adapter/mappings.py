from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScalarMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    encode: str = Field(..., min_length=1, description="读取 item 的 SV 表达式")
    decode: str = Field("", description="从 gp 写入 item 的 SV 语句")


class BufferMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member: str = Field("data", min_length=1, description="item 中的成员路径")
    kind: Literal["packed", "fixed", "dynamic", "queue"] = Field(
        "queue", description="成员容器类型"
    )
    element_bits: int = Field(8, ge=1, le=65536, description="每个元素的有效位数")
    byte_order: Literal["little", "big"] = Field("little", description="元素内字节顺序")
    count: str | None = Field(None, description="编码元素数表达式，省略时取成员容量")
    pack_body: str | None = Field(None, description="自定义编码函数体，操作 item 与 bytes 并返回成功位")
    unpack_body: str | None = Field(None, description="自定义解码函数体，操作 bytes 与 item 并返回成功位")

    @model_validator(mode="after")
    def _paired_bodies(self):
        """检查自定义转换是否包含两个方向。"""
        if (self.pack_body is None) != (self.unpack_body is None):
            raise ValueError("pack_body and unpack_body must be supplied together")
        return self
