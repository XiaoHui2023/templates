from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Models(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_prefix: str = Field("general_", pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", description="类型名前缀，建议以下划线结尾。")
    mode: Literal["address", "ordered", "set"] = Field("address", description="按地址、按顺序或按多重集合匹配。")
    reuse_read_expectations: bool = Field(False, description="读期望在本轮内保留复用，写期望逐个消费。")
    require_golden: bool = Field(True, description="要求本轮至少收到一包合法 golden 输入。")
    require_match: bool = Field(True, description="要求本轮至少成功匹配一个比较单元。")
    atomize: bool = Field(True, description="按有效字节比较。")
    match_address: bool = Field(True, description="将地址作为匹配条件。")
    match_command: bool = Field(False, description="将读写命令作为匹配条件。")
    compare_address: bool = Field(True, description="比较地址。")
    compare_command: bool = Field(True, description="比较读写命令。")
    compare_data: bool = Field(True, description="比较有效字节的数据。")
    compare_response: bool = Field(False, description="比较响应状态。")
    monitor_policy: Literal["drop", "buffer", "strict"] = Field("drop", description="无关 monitor 数据的处理：丢弃、缓存至结束或严格检查。")
    max_pending: int = Field(65536, ge=1, le=2147483647, description="每个输入方向实际保留的比较单元数量上限，包含已覆盖的读模型。")
    max_keys: int = Field(1048576, ge=1, le=2147483647, description="一次复位期间可登记的 golden 匹配条件数量上限。")
    max_payload_bytes: int = Field(1048576, ge=1, le=2147483647, description="单个输入包的有效数据字节数上限。")
