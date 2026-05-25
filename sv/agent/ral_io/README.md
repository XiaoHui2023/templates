# ral_io

用于 UVM RAL 的 agent。

- 对配置的寄存器块注册读写回调；寄存器读写发生时，可取得本次访问对应的寄存器与读写数据
- 配置了写出路径时，仿真结束会把回调捕获的写操作写成 CSV

# ports

| port | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| `o_ap` | output | `uvm_tlm_generic_payload` | RAL 回调输出：块及其子树寄存器的读写 |

# config_db

| key | 类型 | 说明 |
| --- | --- | --- |
| `regmodel` | `uvm_reg_block` | 基寄存器块（必填）；默认 `uvm_reg_map` 用于地址与回调 |
| `init_file` | `string` | 非空时在 main_phase 按序加载并写寄存器 |
| `dump_file` | `string` | 非空时将回调捕获的写操作在仿真结束时写成 CSV |

# 相关文档

- [Sequencer 对外接口](docs/api.md)
