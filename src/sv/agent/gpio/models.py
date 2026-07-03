from typing import List

from pydantic import BaseModel, Field


class Models(BaseModel):
    class_prefix: str = Field("gpio_", description="默认类名的前缀")
    class_regmodel: str = Field(..., description="寄存器模型类名")
    groups: List[str] = Field(..., description="组合")
