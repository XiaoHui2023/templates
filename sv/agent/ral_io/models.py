from pydantic import BaseModel, Field


class Models(BaseModel):
    class_prefix: str = Field(
        "reg_io_",
        min_length=1,
        description="生成类型名所用前缀；`csv_row`、`addr_hit`、`reg_monitor_cb`、`ral_bridge` 子程序名、`sequencer` 与 `agent` 的类型名均带此前缀。",
    )
    input_port_name: str = Field(
        "i_ap",
        min_length=1,
        pattern=r"^[A-Za-z_][A-Za-z0-9_$]*$",
        description="对外 input analysis port 声明名（TLM 写事务入口）。",
    )
    monitor_port_name: str = Field(
        "mon_ap",
        min_length=1,
        pattern=r"^[A-Za-z_][A-Za-z0-9_$]*$",
        description="RAL 回调监控 analysis port 声明名（载荷类型 `uvm_tlm_generic_payload`）。",
    )
    output_port_name: str = Field(
        "replay_ap",
        min_length=1,
        pattern=r"^[A-Za-z_][A-Za-z0-9_$]*$",
        description="sequencer `load_csv(..., emit_replay=1)` 时发出写事务的重放口声明名；`init_file` 不经该口。",
    )
