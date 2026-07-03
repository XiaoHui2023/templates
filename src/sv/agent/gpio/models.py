from typing import List

from pydantic import BaseModel, Field


class Group(BaseModel):
    name: str = Field(..., description="组合名")
    num: int = Field(32, ge=1, le=32, description="GPIO 位宽")


class Models(BaseModel):
    class_prefix: str = Field("gpio_", description="默认类名的前缀")
    class_regmodel: str = Field(..., description="寄存器模型类名")
    groups: List[Group] = Field(..., description="组合")
