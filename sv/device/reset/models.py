from typing import List
from pydantic import BaseModel, Field


class Models(BaseModel):
    class_prefix: str = Field("reset_vip_", description="默认类名前缀")

    def model_post_init(self,ctx):
        pass
