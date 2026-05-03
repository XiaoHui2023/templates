from typing import List, Literal
from pydantic import BaseModel, Field, model_validator


class Models(BaseModel):
    # time_width: 时间位宽
    # data_width: 数据位宽

    class_prefix: str = Field(..., description="默认类名前缀")
    class_signal_io: str = Field(..., description="signal_io的对象名")
    class_struct: str = Field(..., description="struct对象名")
    class_interface: str = Field(..., description="interface对象名")

    reset_signal_name: str = Field("rst_n", description="复位信号名")
    signals: List[str] = Field(..., description="信号列表")

    time_width: str = "64"
    data_width: str = "(256*8)"

    all_signals: List[str] = []

    @model_validator(mode="after")
    def _post_init(self):
        if not self.class_signal_io:
            self.class_signal_io = f"{self.class_prefix}signal_io"
        if not self.class_struct:
            self.class_struct = f"{self.class_signal_io}_struct"
        if not self.class_interface:
            self.class_interface = f"{self.class_signal_io}_interface"

        self.all_signals = self.signals + [self.reset_signal_name]
        return self
