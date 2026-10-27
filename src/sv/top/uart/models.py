from pydantic import BaseModel, ConfigDict, Field


class Models(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_prefix: str = Field("uart_", pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$", description="类型名前缀，建议以下划线结尾。")
    baud_rate: int = Field(115200, ge=1, le=100000000, description="初始串口波特率，单位 bit/s。")
