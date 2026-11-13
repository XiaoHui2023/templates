from pydantic import BaseModel, ConfigDict, Field

from mappings import BufferMapping, ScalarMapping


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
    streaming_width: ScalarMapping = Field(default_factory=lambda: ScalarMapping(encode="gp.get_data_length()"), description="每拍字节数映射")
    data_length: ScalarMapping | None = Field(None, description="数据有效字节数映射，省略时使用编码缓冲区长度")
    max_bytes: int = Field(1048576, ge=1, le=2147483647, description="单次转换允许的缓冲区字节上限")
    encode_hook: str = Field("return 1;", description="编码后的 SV 函数体，可设置 GP 扩展并返回成功位")
    decode_hook: str = Field("return 1;", description="解码后的 SV 函数体，可读取 GP 扩展并返回成功位")
