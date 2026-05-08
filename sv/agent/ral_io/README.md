# ral_io

生成基于 UVM RAL 的 agent：对配置的寄存器块注册读写回调，经监控口输出 `uvm_tlm_generic_payload`；可选将回调捕获的写操作在仿真结束时写成 CSV。TLM 写入口仍可将事务写回寄存器模型。CSV 列为点分路径与数值。

`class_prefix`、`input_port_name`、`monitor_port_name`、`output_port_name` 以同目录 `models.py` 中各字段说明为准。

# 使用方式

环境中通过 `uvm_config_db` 设置基寄存器块；可选 `init_file`、`dump_file`。将外部写事务接到 input port；需要观察经 `load_csv` 重放的写事务时连接 `output_port_name`；需要观察所有经 RAL 回调可见的读写时连接 `monitor_port_name`。

`init_file` 非空时，在仿真主阶段按顺序加载 CSV 并写寄存器（会占用仿真时间直至写序列结束），**不**向重放口发 payload；每次成功写入会打印一行寄存器路径与数值。`dump_file` 非空时：仿真开始时清空待写出的写记录队列，若与 `init_file` 不同路径则截断该文件；仿真结束时将累积的写记录写入该 CSV。

任意时刻在 **sequencer** 上调用 `load_csv` 完成寄存器 CSV 写入（仅此入口对外）；若 `emit_replay` 为 1，同时向重放口发出对应写事务（与 `init_file` 行为不同）。

# ports

| port | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| `input_port_name` | input | `uvm_analysis_port #(uvm_tlm_generic_payload)` | 外部写事务；解析并写回寄存器模型 |
| `monitor_port_name` | output | 同上 | RAL 回调监控：块及其子树寄存器的读写 |
| `output_port_name` | output | 同上 | 仅 `load_csv(..., emit_replay=1)` 时发出写事务 |

# config_db

| key | 类型 | 说明 |
| --- | --- | --- |
| `reg_block` | `uvm_reg_block` | 基寄存器块（必填）；默认 `uvm_reg_map` 用于地址与回调 |
| `init_file` | `string` | 非空时在 main_phase 按序加载并写寄存器；不经重放口 |
| `dump_file` | `string` | 非空时将回调捕获的写操作在仿真结束时写成 CSV |

# 常用 API

详见 [docs/reg_io_api.md](docs/reg_io_api.md)。
