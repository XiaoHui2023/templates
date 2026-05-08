# reg_access_sink

该 agent 仅接收 `uvm_tlm_generic_payload` 写事务：按载荷地址在 RAL 根块子树中定位寄存器，并对所选 `uvm_reg_map` 做前门写，使模型侧与总线上观察到的写配置一致。

`class_prefix`、`input_port_name` 等字段的含义以同目录 `models.py` 中各 `Field(..., description=...)` 为准。

# 使用方式

在环境中通过 `uvm_config_db` 设置起始寄存器块（及可选的 map 名）；将上游 monitor 或 scoreboard 的 analysis 端口接到本 agent 对外的 input analysis port。对命中的寄存器通过该 map 的前门写与 RAL 对接；请按 UVM 惯例为所用 map 接好 sequencer 与总线 adapter。仅处理写方向事务；命中且写成功时打印路径、地址与数据摘要，未命中或写失败则报错。

# ports

| port | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| `i_ap` | input | `uvm_analysis_port #(uvm_tlm_generic_payload)` | 写方向 generic payload 输入；地址与数据字节长度须与 RAL 中该寄存器在 map 上的一致方可命中 |

`input_port_name` 可为其它合法 SystemVerilog 标识符；代码中的端口名与该字段一致。

# config_db

在 **agent** 实例路径上设置：

| key | 类型 | 说明 |
| --- | --- | --- |
| `reg_block` | `uvm_reg_block` | 地址解析与查找的根寄存器块（必填） |
| `reg_map` | `string` | 非空时使用该名字的 `uvm_reg_map`，否则使用根块的默认 map |
