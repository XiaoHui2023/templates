# ral_app

该 agent 仅接收 `uvm_tlm_generic_payload` 写事务：按载荷地址在 RAL 根块子树中定位寄存器，并对根块的默认 `uvm_reg_map` 做前门写，使寄存器模型与总线上观察到的写一致。

`class_prefix`、`input_port_name` 的含义以同目录 `models.py` 中各 `Field(..., description=...)` 为准。

# 使用方式

在环境中通过 `uvm_config_db` 设置起始寄存器块；将上游 monitor 或 scoreboard 的 analysis 端口接到本 agent 对外的 input analysis port。对命中的寄存器经根块默认 map 做前门写；请为该 map 接好 sequencer 与总线 adapter。非写命令会被忽略；地址与数据字节宽度须与 RAL 中该寄存器在该 map 上的一致方可命中；命中且写成功时报告路径、地址与数据摘要，未命中或写失败则报错。

# ports

| port | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| `i_ap` | input | `uvm_analysis_port #(uvm_tlm_generic_payload)` | 写方向 generic payload；声明名与 `input_port_name` 一致 |

# config_db

在 **agent** 实例路径上设置：

| key | 类型 | 说明 |
| --- | --- | --- |
| `reg_block` | `uvm_reg_block` | 地址解析与查找的根寄存器块（必填）；使用其默认 `uvm_reg_map` |
