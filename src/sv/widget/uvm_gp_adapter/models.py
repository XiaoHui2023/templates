from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mappings import BufferMapping, ConstantField, LengthMapping, ScalarMapping


class Models(BaseModel):
    model_config = ConfigDict(extra="ignore")

    class_name: str = Field("uvm_gp_adapter", pattern=r"^[A-Za-z_][A-Za-z0-9_$]*$", description="组件类名")
    item_type: str = Field(..., min_length=1, description="用户数据类型")
    item_is_class: bool = Field(False, description="用户类型是否为类")
    create_item: str = Field("new()", min_length=1, description="解码时创建类对象的表达式")
    data: BufferMapping = Field(default_factory=BufferMapping, description="数据缓冲区映射")
    byte_enable: BufferMapping | None = Field(None, description="字节使能映射")
    address: ScalarMapping = Field(default_factory=lambda: ScalarMapping(encode="0"), description="地址映射")
    command: ScalarMapping = Field(default_factory=lambda: ScalarMapping(encode="UVM_TLM_WRITE_COMMAND"), description="命令映射")
    response_status: ScalarMapping = Field(default_factory=lambda: ScalarMapping(encode="UVM_TLM_INCOMPLETE_RESPONSE"), description="响应映射")
    streaming_width: LengthMapping = Field(default_factory=lambda: LengthMapping(encode="gp.get_data_length()"), description="每拍字节数映射")
    data_length: LengthMapping | None = Field(None, description="数据有效字节数映射，省略时使用编码缓冲区长度")
    byte_enable_length: LengthMapping | None = Field(None, description="字节使能有效长度映射")
    constants: list[ConstantField] = Field(default_factory=list, description="转换表达式使用的常量")
    allowed_commands: list[Literal["read", "write", "ignore"]] = Field(default_factory=lambda: ["read", "write", "ignore"], min_length=1, description="允许的GP命令")
    address_bits: int = Field(64, ge=1, le=64, description="地址有效位数，超出范围拒绝转换")
    byte_enable_policy: Literal["preserve", "disabled", "all_enabled", "required", "full_length"] = Field("preserve", description="字节使能处理策略")
    require_streaming_width: bool = Field(True, description="读写命令是否要求非零streaming width")
    max_bytes: int = Field(1048576, ge=1, le=2147483647, description="单次转换允许的缓冲区字节上限")
    encode_hook: str = Field("return 1;", description="编码后的 SV 函数体，可设置 GP 扩展并返回成功位")
    decode_hook: str = Field("return 1;", description="解码后的 SV 函数体，可读取 GP 扩展并返回成功位")

    @model_validator(mode="after")
    def _policies(self):
        """检查策略与映射的组合是否完整。"""
        names = [entry.name for entry in self.constants]
        reserved = {"item", "gp", "bytes", "raw", "length_value", "address_value", "m_statistics", "to_gp", "from_gp", "last_error", "get_statistics", "clear_statistics"}
        if len(names) != len(set(names)) or reserved.intersection(names):
            raise ValueError("constant names must be unique and not shadow adapter symbols")
        if len(self.allowed_commands) != len(set(self.allowed_commands)):
            raise ValueError("allowed_commands contains duplicates")
        if self.data.encoding != "raw":
            raise ValueError("bit_enable encoding is only valid for byte_enable")
        if self.byte_enable_policy in {"disabled", "all_enabled"} and (self.byte_enable is not None or self.byte_enable_length is not None):
            raise ValueError("disabled/all_enabled policy owns the mask; omit byte_enable mappings")
        if self.byte_enable_policy in {"required", "full_length"} and self.byte_enable is None:
            raise ValueError("required/full_length policy needs byte_enable mapping")
        if self.byte_enable_length is not None and self.byte_enable is None:
            raise ValueError("byte_enable_length needs byte_enable mapping")
        return self
