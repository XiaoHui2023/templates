from pydantic import BaseModel, ConfigDict, Field


class Models(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_prefix: str = Field("reset_vip_", description="类型名前缀。")
    pre_reset_cycles: int = Field(
        10,
        ge=0,
        description="复位拉低前保持释放状态的时钟拍数。",
    )
    reset_asserted_cycles: int = Field(
        10,
        ge=0,
        description="复位拉低期间的时钟拍数。",
    )
    post_reset_cycles: int = Field(
        10,
        ge=0,
        description="复位释放后继续等待的时钟拍数。",
    )
