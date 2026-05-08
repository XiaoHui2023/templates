# ral_io

生成基于 UVM RAL 的 agent。

- 对配置的寄存器块注册读写回调；寄存器读写发生时，可取得本次访问对应的寄存器与读写数据
- 配置了写出路径时，仿真结束会把回调捕获的写操作写成 CSV

# 使用方式

- 用 **`uvm_config_db`** 注入基寄存器块；是否使用 CSV 初始化、是否在仿真结束写出写记录等，按需注入对应路径字符串
- 若配置了从 CSV 初始化寄存器的路径
  - 按序将 CSV 内容写入寄存器模型
  - 每次成功写入可打印路径与数值
- 若配置了仿真结束时写出寄存器写记录的路径：
  - 仿真开始时清空待写出队列
  - 用于初始化的路径与写出路径不是同一个文件时，仿真开始时先清空要写出的那个文件
  - 仿真结束时将累积写记录写入该路径
- 可在 **sequencer** 上按 [常用 API](docs/reg_io_api.md) 做寄存器 CSV 写入

# ports

| port | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| `o_ap` | output | `uvm_analysis_port #(uvm_tlm_generic_payload)` | RAL 回调输出：块及其子树寄存器的读写 |

# config_db

| key | 类型 | 说明 |
| --- | --- | --- |
| `regmodel` | `uvm_reg_block` | 基寄存器块（必填）；默认 `uvm_reg_map` 用于地址与回调 |
| `init_file` | `string` | 非空时在 main_phase 按序加载并写寄存器 |
| `dump_file` | `string` | 非空时将回调捕获的写操作在仿真结束时写成 CSV |

# 常用 API

[docs/reg_io_api.md](docs/reg_io_api.md)
