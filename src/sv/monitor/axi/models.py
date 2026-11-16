from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Models(BaseModel):
    model_config = ConfigDict(extra="ignore")

    class_prefix: str = Field("axi_", pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", description="类型名前缀。")
    protocol: Literal["AXI3", "AXI4", "AXI4_LITE"] = Field("AXI4", description="AXI 协议版本。")
    data_width: Literal[32, 64, 128, 256, 512, 1024] = Field(64, description="数据位宽。")
    addr_width: int = Field(32, ge=1, le=64, description="地址位宽。")
    id_width: int = Field(4, ge=1, le=32, description="事务 ID 位宽。")

    @model_validator(mode="after")
    def validate_lite_width(self) -> "Models":
        """检查 AXI4-Lite 数据位宽。

        Returns:
            配置: 检查通过的配置。

        Raises:
            ValueError: AXI4-Lite 数据位宽不是 32 或 64。
        """
        if self.protocol == "AXI4_LITE" and self.data_width not in (32, 64):
            raise ValueError("AXI4_LITE data_width must be 32 or 64")
        return self
