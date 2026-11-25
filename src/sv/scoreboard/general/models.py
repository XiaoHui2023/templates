from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Models(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_prefix: str = Field("general_", pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", description="类型名前缀，建议以下划线结尾。")
    mode: Literal["address", "ordered", "set", "state"] = Field("address", description="按地址、按顺序、按多重集合或按地址写入终态比较。")
    reuse_read_expectations: bool = Field(False, description="在事务模式中复用读期望，写期望仍逐个消费。")
    expected_units: int = Field(-1, ge=-1, le=9223372036854775807, description="预期比较单元数，-1 自动推导；state 按独立有效字节地址计，其余按 golden 转换单元计。")
    require_golden: bool = Field(True, description="未显式设置预期单元数时，要求至少收到一包合法 golden。")
    require_match: bool = Field(True, description="未显式设置预期单元数时，要求至少成功匹配一个比较单元。")
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

    @model_validator(mode="after")
    def validate_state_policy(self) -> "Models":
        """Reject settings without a byte-addressed write-state interpretation.

        Returns:
            The validated comparison configuration.

        Raises:
            ValueError: State mode conflicts with packet, identity or read reuse settings.
        """
        if self.mode == "state" and (not self.atomize or not self.match_address or self.reuse_read_expectations):
            raise ValueError("state mode requires atomize and match_address, and excludes read expectation reuse")
        return self
