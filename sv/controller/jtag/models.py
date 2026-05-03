from pydantic import BaseModel, Field


class Models(BaseModel):
    class_prefix: str = Field("jtag_ctrl_", description="默认设备的前缀")
    def model_post_init(self, ctx):
        pass
