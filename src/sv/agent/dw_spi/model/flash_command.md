# Flash Command Model

`model/flash_command` 把每个 SPI flash 指令建模为一个配置包。基础包只描述通用 SPI flash transaction 形态；具体 NOR、NAND、3-byte/4-byte address、XIP、厂商扩展指令都应该落到各自的派生指令包中。

控制器 agent 不识别也不验证实际挂载的 flash 类型。用户要执行什么指令，就创建或调用对应指令包；挂载的 flash 是否支持该指令由环境和 flash model 负责。

## 分层

| 层 | 职责 |
| --- | --- |
| `flash_command` | 基础指令包，保存 opcode、frame/transfer mode、指令/地址/数据线宽、dummy、payload 方向和 scoreboard side effect |
| 具体指令文件 | 只写本指令的约束，例如 opcode、地址相位线宽、payload 方向、QE 需求 |
| `flash_command_adapter` | flow 内的通用适配器，把任意 `flash_command` 转换为 `transfer_req` |
| `transfer_seq` | 通用执行 primitive transfer，负责寄存器配置、DR/DMA、CS、completion、scoreboard |

## 基础字段

| 字段 | 说明 |
| --- | --- |
| `opcode` | SPI flash 指令码 |
| `frame_mode` | `STANDARD` 或 `ENHANCED` |
| `transfer_mode` | 控制器 `TMOD`，例如 program 使用 `TX_ONLY`，read 使用 `EEPROM_READ` |
| `io_lanes` | data phase 线宽 |
| `instruction_lanes` | instruction phase 线宽 |
| `address_lanes` | address phase 线宽，不能从 data 线宽一刀切推导 |
| `speed_multiplier` | 映射到 `CTRLR0.SPI_FRF` 的 1/2/4 倍速 |
| `inst_bytes` | instruction phase 字节数；当前内置 flash command 默认 1 |
| `addr_bytes` | address phase 字节数；command-only 指令可为 0，默认 NOR-like flow 使用 3，可配置为 4 |
| `dummy_cycles` | dummy/wait cycles |
| `rx_skip_bytes` | 接收完成后丢弃的前导 byte 数；默认 0 |
| `payload_is_read` / `payload_is_write` | payload 方向 |
| `records_memory_write` | 本指令完成后是否更新 scoreboard memory mirror |
| `requires_qe` | 本指令是否要求 QE 已置位 |

## 当前内置指令包

这些内置包覆盖常见 SPI NOR 显式读写流程，作为 `flash_read`、`flash_write`、`rw_test` 的默认便捷路径。SPI NAND、XIP、厂商特殊状态/feature/page-cache 指令应新增自己的指令包和 flow/kit 快捷入口。

| 文件 | 类 | Opcode | 相位规则 |
| --- | --- | ---: | --- |
| `write_enable.sv` | `write_enable_flash_command` | `0x06` | command-only，标准单线，`TX_ONLY` |
| `write_status_qe.sv` | `write_status_qe_flash_command` | `0x01` | command + 2-byte status data，标准单线，`TX_ONLY`，不更新 memory mirror |
| `page_program.sv` | `page_program_flash_command` | `0x02` | opcode/address 单线，payload 1 线，`TX_ONLY` |
| `dual_page_program.sv` | `dual_page_program_flash_command` | `0xA2` | opcode/address 单线，payload 2 线，`TX_ONLY` |
| `quad_page_program.sv` | `quad_page_program_flash_command` | `0x32` | `1S-1S-4S`：opcode/address 单线、payload 四线，`TX_ONLY`，需要 QE |
| `read1x.sv` | `read1x_flash_command` | `0x03` | opcode/address 单线，payload 1 线，支持 standard/enhanced `EEPROM_READ` |
| `read2x.sv` | `read2x_flash_command` | `0xBB` | opcode 单线，address/data 2 线，`EEPROM_READ`，接收后丢弃 `addr_bytes` 个前导 byte |
| `read4x.sv` | `read4x_flash_command` | `0xEB` | opcode 单线，address/data 4 线，`EEPROM_READ`，要求 QE，接收后丢弃 3 个前导 byte |

`DREAD 0x3B`、`QREAD 0x6B`、erase、RDSR/WIP polling、NAND page read/cache read/program load/program execute 等还没有进入当前可执行 flow。加入时应新增对应指令包，不把 opcode 和相位规则散写在 sequence 里。

## 兼容性规则

- 基础 `transfer_req` 不强制 `FLASH_SPI` 必须有 3/4-byte address；command-only、status、feature、NAND cache 等指令可以没有地址或使用特殊地址形态。
- 普通便捷读写默认 `addr_bytes = 3`，可传入 4 支持 NOR 4-byte address。
- 通用 command packet 可以只表达 SPI bus transaction，不表达 flash 型号。需要具体型号行为时，通过派生指令包、flow sequence、flash model、scoreboard 策略逐层增加。
- 新增某个 flash 类型或型号时，优先增加指令包和文档，再决定是否需要新的 kit shortcut。
- 不要把 `STANDARD` / `ENHANCED` 一律当成指令语义。某些 opcode 的协议相位是固定的，但控制器可以选择 standard 或 enhanced 1x 路径驱动；这类指令包应允许两种 `frame_mode`，由 flow 的 `transfer_configuration` 约束。当前 `READ1X 0x03`、`WREN 0x06`、`WRSR 0x01`、`PP 0x02` 属于这种情况。`DPP/QPP/READ2X/READ4X` 这类 opcode 自身依赖 2x/4x 相位，仍固定为 enhanced。
- Program/write command packets force `dummy_cycles == 0`。Dummy/wait cycles 只用于 read/receive 类 transaction。

## 使用流程

1. flow sequence 创建一个具体 `flash_command`。
2. flow 用本次 `transfer_configuration` 约束 `addr_bytes`、`data_frame_bits` 等运行期形态；dummy cycle 由具体 read command packet 约束。
3. flow 调用 `flash_command_adapter.create_transfer_req()`。
4. flow 把生成的 `transfer_req` 交给 `transfer_seq`。

新增指令时先加 `model/flash_command/<name>.sv.j2` 和本文档，再在 flow 中组合该指令包。

## Read Dummy Cycles

| Command | Opcode | Dummy SCLK cycles | Controller path |
| --- | ---: | ---: | --- |
| `READ1X` | `0x03` | 0 | standard 从 `DR` 发送 opcode/address；enhanced 由 `SPI_CTRLR0` 描述控制阶段；两者随后进入 RX |
| `READ2X` | `0xBB` | 4 | enhanced `EEPROM_READ`，`SPI_CTRLR0.WAIT_CYCLES`；`rx_skip_bytes=addr_bytes` |
| `READ4X` | `0xEB` | 6 | enhanced `EEPROM_READ`，`SPI_CTRLR0.WAIT_CYCLES`；`rx_skip_bytes=3` |

这些值属于 opcode command packet，不属于 `transfer_configuration` 的全局默认值。
