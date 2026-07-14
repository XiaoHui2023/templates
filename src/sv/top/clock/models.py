from pydantic import BaseModel, Field


class Models(BaseModel):
    class_name: str = Field("Clock_interface", description="clock interface name")
