from typing import List, Literal
from pydantic import BaseModel, Field, model_validator


class Models(BaseModel):
    class_name: str = Field(..., description="??")
    port_name: str = Field('i_ap', description="???")
