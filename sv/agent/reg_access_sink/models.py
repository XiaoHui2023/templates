from pydantic import BaseModel, Field


class Models(BaseModel):
    class_prefix: str = Field(
        "tb_",
        min_length=1,
        description="SystemVerilog 类名前缀；数据类、agent 与辅助类名均带此前缀，agent 类名为前缀后接 agent。",
    )
    input_port_name: str = Field(
        "i_ap",
        description="对外 input analysis port 名（须为合法 SystemVerilog 标识符）。",
    )
