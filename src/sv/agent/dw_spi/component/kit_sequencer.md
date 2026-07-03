# kit_sequencer

`kit_sequencer` 是 `sequencer` 的便捷 facade。

它只负责创建 req/seq、补默认参数、启动 sequence、汇总 output。不要在 `kit_sequencer` 中实现寄存器配置、传输执行、scoreboard 比较或 callback 行为。

## 快捷入口

### `init_registers`

根据一个 `transfer_req` 生成并写入本次传输需要的寄存器配置。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `transfer_req` | `dw_spi_transfer_req` | 本次传输的协议形态和 payload |

### `flash_write`

启动 flash 写 flow。地址是 flash/model 地址，不是寄存器地址。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `address` | `bit [63:0]` | flash 起始地址 |
| `data` | `bit [7:0] $` | 写入数据 |

### `flash_read`

启动 flash 读 flow。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `data` | `output bit [7:0] $` | 读回数据 |
| `address` | `bit [63:0]` | flash 起始地址 |
| `length` | `int unsigned` | 读长度 |

### `check_clocks`

启动可选时钟检查 operation。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `result` | `output dw_spi_check_clock_rsp` | 检查结果 |

### `rw_test`

启动读写测试场景：写入数据、读回数据，并把结果交给 scoreboard 比较。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `result` | `output dw_spi_rw_test_rsp` | 测试结果 |
| `address` | `bit [63:0]` | flash 起始地址 |
| `write_data` | `bit [7:0] $` | 写入数据 |
| `actual_read_data` | `bit [7:0] $` | 可选外部实际读回数据 |

## 边界

`kit_sequencer` 不提供通用 `reg_write` / `reg_read`。寄存器地址、通用读写策略、寄存器查找都由 regmodel 托管；DW SPI sequence/core 只在具体操作里调用明确的 `settings.regmodel.<reg>.write/read`。
