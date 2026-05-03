from typing import List, Literal
from pydantic import BaseModel, Field, model_validator


class Models(BaseModel):
    class_prefix: str = Field(..., description="类名前缀")
    class_interface: str = Field(..., description="interface类名")
    class_monitor: str = Field(..., description="monitor类名")

    out_port_name: str = Field("o_ap", description="输出端口名字")

    @model_validator(mode="after")
    def _post_init(self):
        if not self.class_interface:
            self.class_interface = f"{self.class_prefix}fifo_interface"
        if not self.class_monitor:
            self.class_monitor = f"{self.class_prefix}fifo_monitor"
        return self
