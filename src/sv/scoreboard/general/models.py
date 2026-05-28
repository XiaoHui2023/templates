from typing import List, Literal
from pydantic import BaseModel, Field, model_validator


class Models(BaseModel):
    class_name: str = Field(..., description="??")
    golden_port_name: str = Field('gld_ap', description="golden???")
    monitor_port_name: str = Field('mon_ap', description="monitor???")
