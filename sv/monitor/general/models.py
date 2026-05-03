from typing import List, Literal
from pydantic import BaseModel, Field, model_validator


class Models(BaseModel):
    class_prefix: str = Field('', description="默认类名前缀")
    class_monitor: str = Field('', description="monitor组件类名")
    class_interface: str = Field('', description="interface类名")

    @model_validator(mode='after')
    def _post_init(self):
        if not self.class_monitor:
            self.class_monitor = f"{self.class_prefix}general_monitor"
        if not self.class_interface:
            self.class_interface = f"{self.class_prefix}general_interface"
        return self
