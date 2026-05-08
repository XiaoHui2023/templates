from pydantic import BaseModel, Field


class Models(BaseModel):
    class_prefix: str = Field(
        "tb_",
        min_length=1,
        description="生成类型名所用前缀；`addr_hit`、`ral_apply` 与 agent 的类型名均带此前缀，agent 类型名为前缀后接 `agent`。",
    )
    input_port_name: str = Field(
        "i_ap",
        min_length=1,
        pattern=r"^[A-Za-z_][A-Za-z0-9_$]*$",
        description="对外 input analysis port 名。",
    )
