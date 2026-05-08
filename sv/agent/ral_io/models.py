from pydantic import BaseModel, Field


class Models(BaseModel):
    class_prefix: str = Field(
        "reg_io_",
        min_length=1,
        description="生成类型名所用前缀；`csv_row`、`addr_hit`、`ral_bridge` 中子程序名、`sequencer` 与 `agent` 的类型名均带此前缀。",
    )
    input_port_name: str = Field(
        "i_ap",
        min_length=1,
        pattern=r"^[A-Za-z_][A-Za-z0-9_$]*$",
        description="对外 input analysis port 声明名（TLM 写事务入口）。",
    )
    output_port_name: str = Field(
        "o_ap",
        min_length=1,
        pattern=r"^[A-Za-z_][A-Za-z0-9_$]*$",
        description="CSV 初始化或 `load_csv` 产生写事务的 output analysis port 声明名。",
    )
