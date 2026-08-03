# Sequence Flows

`sequence` 目录承载执行流程。`operation` 是具体动作，`flow` 组合多个 operation，`test` 组合可复用场景。sequencer 只保存句柄和 callback wrapper；kit_sequencer 只提供快捷启动入口。

## Clock Check

1. `check_clock_seq` 从 `p_sequencer.settings.vif` 获取 top interface。
2. 检查 `hclk` 和 `ssi_clk` 是否连接；X/Z 视为未连接。
3. 已连接且 req 要求检查时，采样一个完整周期并计算整数 Hz。
4. 与各自最低频率比较，默认最低 24 MHz，默认容差 1%。
5. 不检查 `sclk_out`，也不检查 `hclk` 与 `ssi_clk` 的频率关系。

`ssi_clk` 是控制器输入参考时钟。`sclk_out = ssi_clk / BAUDR`，由 register configuration 阶段根据公式推导。

## Init Registers

1. `init_registers_seq` 接收一个 `transfer_req`。
2. `register_config_builder` 根据 transfer req 和 settings 生成 `configuration`。
3. builder 测量 `ssi_clk`，根据 `target_sclk_hz` 计算偶数 `BAUDR`。
4. builder 根据 `opcode/address/dummy/payload` 的总 byte 数计算实际 NDF；除 `0x06` 这类单 opcode 命令外，连续命令写入 `CTRLR1.NDF = actual_ndf - 1`。如果该编码值超过 `settings.ctrlr1_ndf_max`，立即 fatal。
5. `register_access` 实例化后注入 settings 和 `report_context = p_sequencer`。
6. `register_access.apply_configuration()` 按 FIELD 写 regmodel。

寄存器配置不通过 sequencer 函数完成，不通过 callback 完成，也不在 core 里引用 operation req。

## Primitive Transfer

1. `transfer_seq` 检查 req、payload、scoreboard。
2. 生成本次寄存器 `configuration`。
3. 内置 DMA 写 transfer 在启动控制器前，通过 callback `cpu_write(addr, word, UVM_BACKDOOR)` 把 payload 写入 `axi_addr` 指定的系统内存 buffer。
4. 调用 `register_access.apply_configuration()`。该阶段会关闭控制器、清中断、清 `SER`、配置寄存器、重新使能控制器，但不会选中片选。
5. 非 DMA PIO 构造 DR byte stream。flash 协议包含 opcode、大端地址字节；写传输追加 payload。命令-only 传输 payload 长度为 0，但 DR stream 仍包含 opcode。
   flash write/program 不使用 dummy clock；enhanced read 的 dummy/wait 通过 `SPI_CTRLR0.WAIT_CYCLES` 表达。
6. PIO 在 `SER=0` 时先向 `DR` 预填不超过 `settings.fifo_depth_bytes` 的字节。
7. 到 transaction 边界时选中 CS：`HARDWARE_CS` 写 `SER.SER = cfg.ser`；`SOFTWARE_CS` 先调用 `p_sequencer.activate_chip_select(cs_id)`，再写 `SER.SER = cfg.ser`。
8. PIO 写 transfer 如果还有 remaining byte，会在同一个 CS window 内继续等待 `SR.TFNF` 并补写 `DR`。`TXFTLR` 是硬件 FIFO 阈值配置；当前 sequence 用 `SR.TFNF` 轮询驱动补 FIFO，不把 FIFO interrupt 当 completion。
9. 按 `configuration.completion_mode` 等待 completion。内置 DMA 可用 top `intr` + `ISR.DONES`；非 DMA PIO 使用 `SR.TFE && !SR.BUSY`。
10. 释放 CS：先写 `SER.SER = 0`，如果是 `SOFTWARE_CS` 再调用 `p_sequencer.release_chip_select(cs_id)`。
11. 写传输在 CS 释放后仅对 flash memory program opcode（`0x02/0xA2/0x32`）更新 scoreboard expected data；`WREN/WRSR` 这类状态命令不更新 memory mirror。读传输把从 `DR` 或 DMA buffer 得到的 actual data 放入 rsp。

一个 primitive transfer 对应一个完整 SPI transaction 边界。需要连续的 read opcode + address + dummy + data 或 write opcode + address + data 必须放在同一个 primitive transfer 内，不能拆成多个 CS window。

## Completion Rule

| Mode | 行为 |
| --- | --- |
| `PREFER_INTERRUPT_COMPLETION` | 内置 DMA 且 `intr` 已连接时，等待 top `intr` 并检查 `ISR.DONES`；非内置 DMA 或 `intr` 未连接时，轮询 `SR.TFE && !SR.BUSY`。 |
| `INTERRUPT_COMPLETION` | 只允许内置 DMA。非内置 DMA 使用该模式会 fatal，避免误等不会来的 `ISR.DONES`。 |
| `POLLING_COMPLETION` | 强制轮询 `SR.TFE && !SR.BUSY`。 |

非 DMA PIO 不使用 `ISR.DONES`。如果以后要用中断降低 PIO CPU 占用，需要实现 FIFO/error interrupt 驱动的 PIO 状态机；不能把 `TXEIM/RXFIM` 或 `ISR.DONES` 当普通完成中断。

## Flash Read

1. 未携带 configuration 时创建 `host_configuration` 并 randomize。
2. 根据本次 configuration 创建一个 `model/flash_command` 指令包：1x standard 为 `read1x_flash_command`，1x enhanced 为 `fast_read1x_flash_command`，2x 为 `read2x_flash_command`，4x 为 `read4x_flash_command`。
3. 用 configuration 约束该指令包的 `addr_bytes`、`dummy_cycles`、`data_frame_bits`。
4. 调用 `flash_command_adapter.create_transfer_req()` 生成通用 `transfer_req`，payload command 为 `UVM_TLM_READ_COMMAND`，address 为 flash 地址，data length 为读取长度。
5. 指令包负责 opcode、`RX_ONLY`、address phase 线宽和 data phase 线宽。`READ1X/FASTREAD1X` 是单线地址，`READ2X` 是 2 线地址，`READ4X` 是 4 线地址。
6. 同一个 primitive transfer 内完成 opcode + address + dummy + read data，CS 不能在中间断开。
7. flow sequence 保存 transfer rsp 的 `read_data`，并调用 scoreboard 比较 actual read data。

地址是 32 bit flash/model 地址，不是寄存器地址。

## Flash Write

1. 未携带 configuration 时创建 `host_configuration` 并 randomize。
2. WREN/WRSR/program 都先创建 `model/flash_command` 指令包，再由 `flash_command_adapter` 转成通用 `transfer_req`。
3. 1x/2x program：先启动 `write_enable_flash_command`，opcode `8'h06`，`TX_ONLY`，不使用 DMA。payload 长度为 0，但 PIO DR stream 仍包含 1 byte opcode。该命令独立占用一个 CS window。
4. 4x QPP：先 `WREN 0x06`，再 `WRSR 0x01 + 0x00 + 0x02` 写 16-bit status 值 `0x0200` 以设置 `status[9] / SREG_QE`，然后再次 `WREN 0x06`。WRSR 会清除 WEL，因此 QPP 前必须重新置位 WEL。
5. write-enable 成功后启动 program transfer：1x 用 `page_program_flash_command`，2x 用 `dual_page_program_flash_command`，4x 用 `quad_page_program_flash_command`。所有 program 写命令的 opcode + address 都是单线；payload data phase 才按指令包使用 1/2/4 线。opcode + address + payload 必须在同一个 CS window 内连续发送，写流程不插入 dummy clock。`TX_AND_RX` / `RX_ONLY` 是 enhanced read/EEPROM-read 类接收流程使用的模式，不能用于 page program。
6. payload command 为 `UVM_TLM_WRITE_COMMAND`，address 为 flash 地址，data 为非空写入 byte 队列。`flash_write` 不接受 0 byte program；只有 `rw_test` 的空 `write_data` 表示随机生成默认长度数据。
7. 非 DMA PIO 不因为数据超过 FIFO 就拆成多个 program。它先预填 FIFO，然后在同一个 program CS window 内按 `SR.TFNF` 继续补数据；`CTRLR1.NDF` 仍按完整 `opcode + address + payload` 总量配置。如果完整 payload 使 NDF 超过寄存器上限，则报错，不在该层偷偷拆交易。
8. program transfer 完成并释放 CS 后，operation sequence 记录 expected write 到 scoreboard。

当前模板暂不实现 flash erase `8'hC7`、status poll `8'h05`、跳过已置位 QE 和 256B 分页写限制；这些属于完整 SPI-NOR 行为建模，已作为后续扩展点记录。

## RW Test

读写测试顺序是写后读。

1. 未携带 configuration 时创建 `host_configuration` 并 randomize。
2. `write_data` 为空时随机生成一段数据，长度来自 Python `default_rw_data_bytes`，默认 256 byte。
3. 启动 `flash_write`。
4. 启动同地址同长度的 `flash_read`。
5. 调用 `scoreboard.check_actual_read(address, read_data, "rw_readback_actual")`。比较对象是真实读传输从 `DR` 或 DMA buffer 读回的 actual data。

## DMA Transfer

1. Python 通过 `internal_dma` / `external_dma` 选择生成内置 DMA、外部 DMA 或无 DMA，二者不能同时开启。
2. 无 DMA 时不生成 `use_dma` 和 DMA 寄存器配置。
3. 内置 DMA 时，per-transfer configuration 可设置 `use_dma`、`awlen`、`arlen`、`axi_addr`；builder 转换成 `DMACR.RDMAE/TDMAE/IDMAE/AINC`、DMA threshold、`AXIAWLEN.AWLEN = awlen << 8`、`AXIARLEN.ARLEN = arlen << 8`、`SPIDR.SPI_INST`、`SPIAR.SDAR`、`AXIAR0.AXIAR0`。
4. 内置 DMA 写 transfer 在启动前通过 CPU callback 写 AXI source buffer；读 transfer 在 completion 且释放 CS 后，通过 CPU callback 从 AXI destination buffer 读取 actual data。
5. 外部 DMA 只配置 `DMACR.RDMAE/TDMAE` 和 DMA threshold；外部 DMA engine 完成由环境补齐。
6. 内置 DMA 是当前模板唯一使用 `ISR.DONES` 的完成中断路径。

## Log Verbosity

- `UVM_LOW` 只放日常必须看到的高层事件。对 WREN/program/read 这类完整 flash interaction，低冗余打印 `transfer_req.sprint()`，包内包含 opcode、payload command、address、data length、data preview、mode、CS、lane、speed、dummy 等字段；不要再用手写字符串重复打印同一组字段。
- `UVM_HIGH` 放一次 transfer 内的执行摘要：PIO DR stream preview、CS 选择/释放、FIFO prefill/remaining、SR completion 等待、DMA buffer 汇总、scoreboard 记录摘要。
- `UVM_DEBUG` 打印排障细节：寄存器 raw 值、NDF/BAUDR 推导中间值、寄存器配置步骤、FIFO 状态轮询、逐 byte DR 写读、CPU DMA buffer word、scoreboard byte 比较。
- timeout 报错必须包含 `waiting_for`。中断等待写明 top `intr` 和预期来源；`SR` 轮询写明目标条件和最后一次 `SR` 原始值及字段。

## Flash Type Boundary

默认 `flash_read` / `flash_write` 是 NOR-like 便捷 flow，不代表控制器 agent 固定绑定 NOR。NAND page/cache、XIP、厂商 feature、无地址或特殊地址形态命令应新增 `model/flash_command` 指令包，并按需要新增专用 flow/kit shortcut；基础 transfer 不应强制所有 `FLASH_SPI` 都有 3/4-byte address。

## Internal DMA Instruction Register

For internal DMA, `SPIDR.SPI_INST` is a 16-bit instruction container. Current flash commands use `inst_bytes == 1`, so the builder writes `{opcode, 8'h00}` and relies on `SPI_CTRLR0.INST_L` to select an 8-bit instruction. This keeps `inst_bytes` and the SPIDR container width separate.
