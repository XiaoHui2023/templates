from pydantic import BaseModel, Field


class Models(BaseModel):
    """
    # reg_writer

    生成仅接收 `uvm_tlm_generic_payload` 写事务的 UVM 组件：按载荷中的地址在 RAL
    基块子树中定位寄存器，并对所选 map 做**前门**寄存器写，使模型侧与总线访问一致。
    用于将总线或 TLM 侧观察到的写配置流对接到寄存器模型。

    # 使用方式

    在环境中通过 `uvm_config_db` 设置 **起始寄存器块**（及可选的 map 名）；将上游
    monitor 或 scoreboard 的 analysis 端口接到本组件对外的 `i_ap`。对命中的寄存器
    通过 **该 map 的前门写** 与 RAL 对接（请按 UVM 惯例为所用 map 接好 **sequencer**
    与总线 **adapter**）。仅处理写方向事务；成功时报告路径、地址与写入数据，未命中
    或写失败则报错。

    # ports

    | port | 方向 | 类型 | 说明 |
    | --- | --- | --- | --- |
    | `i_ap` | input | `uvm_analysis_port #(uvm_tlm_generic_payload)` | 写方向 generic payload 输入；地址与数据长度需与 RAL 中该寄存器在 map 上的一致，方可命中 |

    # config_db

    | key | 类型 | 说明 |
    | --- | --- | --- |
    | `reg_block` | `uvm_reg_block` | 地址解析与查找的**根寄存器块**（必填） |
    | `reg_map` | `string` | 可选；非空时使用该名字的 `uvm_reg_map`，否则使用根块的默认 map |
    """

    class_prefix: str = Field(
        "tb_",
        description="生成类名前缀（须非空）；生成类名为前缀接 reg_writer。",
    )
    input_port_name: str = Field(
        "i_ap",
        description="对外 input analysis port 名（须为合法 SystemVerilog 标识符）。",
    )
