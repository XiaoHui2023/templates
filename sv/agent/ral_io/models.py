from pydantic import BaseModel, Field


class Models(BaseModel):
    class_prefix: str = Field(
        "reg_io_",
        min_length=1,
        description="生成类型名所用前缀；`csv_row`、`addr_hit`、`reg_monitor_cb`、`ral_bridge` 子程序名、`sequencer` 与 `agent` 的类型名均带此前缀。",
    )
    o_ap: str = Field(
        "o_ap",
        min_length=1,
        pattern=r"^[A-Za-z_][A-Za-z0-9_$]*$",
        description="RAL 回调所捕事务的 output analysis port 声明名（`uvm_tlm_generic_payload`）。",
    )
