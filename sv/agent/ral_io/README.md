# ral_io

生成通过 CSV 描述寄存器写事务的 UVM agent：两列为点分路径（相对基寄存器块）与数值（常见十六进制或十进制写法）。推荐把 **sequencer** 当作对外操作句柄。

`class_prefix`、`input_port_name`、`output_port_name` 的含义以同目录 `models.py` 中各 `Field(..., description=...)` 为准。

# 使用方式

在环境中通过 `uvm_config_db` 设置基寄存器块与可选的初始化 CSV、写出 CSV 路径；将外部写事务接到 `i_ap`，需要观察 CSV 载入产生的写事务时连接 `o_ap`。初始化与运行过程中可调用 sequencer 的 `load_csv` 将行转为写事务；同时按配置更新寄存器模型并累积待写出的 CSV 行。`dump_file` 非空时：仿真开始时清空待写出行队列，若与 `init_file` 不是同一路径则截断该输出文件；仿真结束时将累积行保存为该路径下的 CSV。同一仿真内多次测试若复用同一 sequencer，下一轮测试前须调用 `clear_dump_rows()`。

# ports

| port | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| `i_ap` | input | `uvm_analysis_port #(uvm_tlm_generic_payload)` | 外部写事务输入；声明名与 `input_port_name` 一致；解析并写回寄存器模型，`dump_file` 非空时记入待写出队列 |
| `o_ap` | output | `uvm_analysis_port #(uvm_tlm_generic_payload)` | CSV 初始化或 `load_csv` 产生的写事务输出；声明名与 `output_port_name` 一致 |

# config_db

| key | 类型 | 说明 |
| --- | --- | --- |
| `reg_block` | `uvm_reg_block` | 点分路径解析与地址编码的起始寄存器块（必填）；使用其默认 `uvm_reg_map` |
| `init_file` | `string` | 非空时自动 `load_csv` 读取该路径并初始化寄存器模型 |
| `dump_file` | `string` | 非空时仿真开始时清空待写出队列，若与 `init_file` 不同路径则截断该文件；仿真结束时写出 CSV |

# 常用 API

详见 [docs/reg_io_api.md](docs/reg_io_api.md)。
