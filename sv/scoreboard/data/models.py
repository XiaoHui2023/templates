from typing import List, Literal
from pydantic import BaseModel, Field, model_validator


class Models(BaseModel):
    class_name: str = Field(..., description="类名")

    gld_port_name: str = Field("gld_ap", description="golden端口名字")
    mon_port_name: str = Field("mon_ap", description="monitor端口名字")
