from typing import List, Literal
from pydantic import BaseModel, Field, model_validator


class Models(BaseModel):
    class_prefix: str = Field(..., description="类名前缀")
    class_scoreboard: str = Field('', description="scoreboard类名")

    golden_port_name: str = Field('gld_ap', description="golden端口名")
    monitor_port_name: str = Field('mon_ap', description="monitor端口名")

    @model_validator(mode='after')
    def _post_init(self):
        if not self.class_scoreboard:
            self.class_scoreboard = f"{self.class_prefix}set_scoreboard"
        return self
