# Sequence Flows

## Failure Contract

- FIFO/status/interrupt waits have bounded timeouts. Timeout errors identify the exact `SR` condition or interrupt source that did not arrive.
- Any operation, flow, or test that finishes with `ok == 0` emits `uvm_error` with its transfer or phase context. Structural failures such as null mandatory handles, invalid configuration, and failed randomization remain `uvm_fatal`.
- Flash reads validate the returned byte count before comparing bytes. Zero-byte or short DMA/DR0 readback cannot pass an empty comparison.
- `rw_test` and `dma_test` verify moved write data by reading it back from the DUT path and comparing it with the scoreboard mirror. The source payload is expected data, not actual observed data.

`sequence` 目录承载执行流程。`operation` 是具体动作，`flow` 组合多个 operation，`test` 组合可复用场景。sequencer 只保存句柄和 callback wrapper；kit_sequencer 只提供快捷启动入口。

## Clock Check

1. `check_clock_seq` 从 `p_sequencer.settings.vif` 获取 top interface。
2. 检查 `hclk` 和 `ssi_clk` 是否连接；X/Z 视为未连接。
3. 已连接且 req 要求检查时，采样一个完整周期并计算整数 Hz。
4. 与各自最低频率比较，默认最低 24 MHz，默认容差 1%。
5. 不检查 `sclk_out`，也不检查 `hclk` 与 `ssi_clk` 的频率关系。

`ssi_clk` 是控制器输入参考时钟。`sclk_out = ssi_clk / BAUDR_logical`，由 register configuration 阶段根据公式推导。DMA 模式写入的 `BAUDR.SCKDV` 为该逻辑分频值的一半。

## Init Registers

1. `init_registers_seq` 接收一个 `transfer_req`。
2. `register_config_builder` 根据 transfer req 和 settings 生成 `configuration`。
3. builder 测量 `ssi_clk`，根据 `target_sclk_hz` 计算偶数逻辑分频值。PIO 令 `configuration.baudr=BAUDR_logical`；DMA 令 `configuration.baudr=BAUDR_logical>>1`，供 `register_access` 写入 `BAUDR.SCKDV`。
4. builder 仅根据 payload byte 数和 DFS 计算 `actual_data_frames`，instruction/address/dummy 不计入 NDF；非零 data frame 数写入 `CTRLR1.NDF = actual_data_frames - 1`。如果该编码值超过 `settings.ctrlr1_ndf_max`，立即 fatal。
5. `register_access` 实例化后注入 settings 和 `report_context = p_sequencer`。
6. `register_access.apply_configuration()` 按 FIELD 写 regmodel。

寄存器配置不通过 sequencer 函数完成，不通过 callback 完成，也不在 core 里引用 operation req。

## Primitive Transfer

1. `transfer_seq` 检查 req、payload、scoreboard。
2. 生成本次寄存器 `configuration`。
3. 内置 DMA 写 transfer 在启动控制器前通过 callback 写 AXI source payload。内置 DMA 读 transfer 不预写 AXI buffer，也不通过 PIO 写 `DR0`。
4. 调用 `register_access.apply_configuration()`。该阶段会关闭控制器、清中断、清 `SER`、配置寄存器、重新使能控制器，但不会选中片选。
5. 非 DMA PIO 构造 DR0 item stream。standard flash 把 opcode、大端地址、dummy 逐 byte 放入 item；enhanced flash 把 opcode 和完整 address 各放入一个 32-bit control item，再追加 payload。命令-only 传输 payload 长度为 0，但 DR0 stream 仍包含 opcode。
   flash write/program 不使用 dummy clock；enhanced read 的 dummy/wait 通过 `SPI_CTRLR0.WAIT_CYCLES` 表达。
6. PIO 在 `SER=0` 时先向 `DR0` 预填不超过 `settings.fifo_depth_bytes` 的 FIFO items。
7. 到 transaction 边界时选中 CS：`HARDWARE_CS` 写 `SER.SER = cfg.ser`；`SOFTWARE_CS` 先调用 `p_sequencer.activate_chip_select(cs_id)`，再写 `SER.SER = cfg.ser`。
8. PIO 写 transfer 如果还有 remaining byte，会在同一个 CS window 内继续等待 `SR.TFNF` 并补写 `DR0`。`TXFTLR` 是硬件 FIFO 阈值配置；当前 sequence 用 `SR.TFNF` 轮询驱动补 FIFO，不把 FIFO interrupt 当 completion。
9. 按 `configuration.completion_mode` 等待 completion。内置 DMA 可用 top `intr` + `ISR.DONES`；非 DMA PIO 使用 `SR.TFE && !SR.BUSY`。
10. 释放 CS：先写 `SER.SER = 0`，如果是 `SOFTWARE_CS` 再调用 `p_sequencer.release_chip_select(cs_id)`。
11. 写传输在 CS 释放后仅对 flash memory program opcode（`0x02/0xA2/0x32`）更新 scoreboard expected data；`WREN/WRSR` 这类状态命令不更新 memory mirror。读传输把从 `DR0` 或 DMA buffer 得到的 actual data 放入 rsp。

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
2. 根据本次 configuration 创建一个 `model/flash_command` 指令包：1x 使用 standard `read1x_flash_command`，2x 使用 enhanced `read2x_flash_command`，4x 使用 enhanced `read4x_flash_command`。
3. 用 configuration 约束 `addr_bytes`、`data_frame_bits`；`frame_mode` 由指令包的倍速约束派生，dummy cycle 由 opcode 指令包决定。
4. 调用 `flash_command_adapter.create_transfer_req()` 生成通用 `transfer_req`，payload command 为 `UVM_TLM_READ_COMMAND`，address 为 flash 地址，data length 为读取长度。
5. 指令包负责 opcode、PIO `EEPROM_READ`、address phase 线宽和 data phase 线宽。内部 DMA adapter 把 READ2X/READ4X 的 primitive transfer mode 改为 `RX_ONLY`。`READ1X` 是单线地址，`READ2X` 是 2 线地址，`READ4X` 是 4 线地址。
6. Standard read 从 `DR0` 连续发送 opcode + address，然后控制器按 `CTRLR1.NDF` 自动切换到 RX。Enhanced read 由 `SPI_CTRLR0` 控制 instruction + address + dummy/wait phase，然后按 NDF 自动切换到 RX。
7. 同一个 primitive transfer 内完成 opcode + address + dummy + read data，CS 不能在中间断开。
8. 指令包的 `rx_skip_bytes` 非零时，transfer 按 `requested_length + rx_skip_bytes` 接收；flow 丢弃指定数量的前导 byte，再保存 `read_data` 并调用 scoreboard 比较。`READ2X` 丢弃 1 byte，`READ4X` 丢弃 3 byte。

地址是 32 bit flash/model 地址，不是寄存器地址。

## Flash Write

1. 未携带 configuration 时创建 `host_configuration` 并 randomize。
2. WREN/WRSR/program 都先创建 `model/flash_command` 指令包，再由 `flash_command_adapter` 转成通用 `transfer_req`。
3. 1x/2x program：先启动 `write_enable_flash_command`，opcode `8'h06`，`TX_ONLY`，不使用 DMA。payload 长度为 0，但 PIO DR0 stream 仍包含 1 byte opcode。该命令独立占用一个 CS window。
4. program 指令包 `requires_qe=1` 时，先运行共享 `flash_enable_qe_seq`：`WREN 0x06`，再 `WRSR 0x01 + 0x00 + 0x02` 写 16-bit status 值 `0x0200`。之后所有 program 都重新发送 `WREN`，再开始连续 program transaction。QPP 声明 `requires_qe=1`，流程不按速度硬编码 QE。
5. write-enable 成功后启动 program transfer：1x 用 `page_program_flash_command`，2x 用 `dual_page_program_flash_command`，4x 用 `quad_page_program_flash_command`。PP、DPP、QPP 的 opcode + address 都为单线；QPP `0x32` 只有 payload 为 4 线，因此配置 `SPI_CTRLR0.TRANS_TYPE=0`、`CTRLR0.SPI_FRF=2`。8-bit opcode 占 8 SCLK，默认 3-byte address 占 24 SCLK。opcode + address + payload 必须在同一个 CS window 内连续发送，写流程不插入 dummy clock。`EEPROM_READ` 等接收流程使用的模式不能用于 page program。
6. payload command 为 `UVM_TLM_WRITE_COMMAND`，address 为 flash 地址，data 为非空写入 byte 队列。`flash_write` 不接受 0 byte program；只有 `rw_test` 的空 `write_data` 表示随机生成默认长度数据。
7. 非 DMA PIO 不因为数据超过 FIFO 就拆成多个 program。它先预填 FIFO，然后在同一个 program CS window 内按 `SR.TFNF` 继续补数据；`CTRLR1.NDF` 按完整 payload 的 data frame 数配置，不包含 opcode/address 两个 enhanced control entries。如果完整 payload 使 NDF 超过寄存器上限，则报错，不在该层偷偷拆交易。
8. program transfer 完成并释放 CS 后，operation sequence 记录 expected write 到 scoreboard。

读指令包也使用同一个 `requires_qe` 决定是否运行 `flash_enable_qe_seq`；当前 READ4X 声明需要 QE。模板暂不实现 flash erase `8'hC7`、status poll `8'h05`、跳过已置位 QE 和 256B 分页写限制。

## RW Test

读写测试顺序是写后读。

1. 未携带 configuration 时创建 `host_configuration` 并 randomize。
2. `write_data` 为空时随机生成一段数据，长度来自 Python `default_rw_data_bytes`，默认 256 byte。
3. 启动 `flash_write`。
4. 启动同地址同长度的 `flash_read`。
5. 调用 `scoreboard.check_actual_read(address, read_data, "rw_readback_actual", write_data.size())`。先检查返回长度，再比较真实读传输从 `DR0` 或 DMA buffer 读回的 actual data。

## DMA Transfer

1. Python 通过 `internal_dma` / `external_dma` 选择生成内置 DMA、外部 DMA 或无 DMA，二者不能同时开启。
2. 无 DMA 时不生成 `use_dma` 和 DMA 寄存器配置。
3. 内置 DMA 时，per-transfer configuration 可设置 `use_dma` 和 `axi_addr`。adapter 固定设置 `AWLEN=15`、`ARLEN=15`，表示 AXI 读写单笔 burst 的最大值均为 16 beat；builder 将四位 `awlen/arlen` 直接写入对应 field，并配置 `AXIAR0.AXIAR0`。软件不根据本次数据量调整 LEN，实际 burst 由控制器自动决定。
4. 内置 DMA 的 READ2X/READ4X 使用 `RX_ONLY`。`SPIDR`、`SPIAR` 和 `SPI_CTRLR0` 提供 instruction、address 和 wait phase；启动前不写 AXI source control item 或 `DR0`。
5. 内置 DMA 写 transfer 在启动前通过 CPU callback 写 AXI source payload；读 transfer 在 completion 且释放 CS 后，通过 CPU callback 从 AXI destination buffer 读取 actual data。
6. 外部 DMA 仍在选择 CS 前向 TX FIFO 预填 read control items，并配置 `DMACR.RDMAE/TDMAE` 和 DMA threshold；外部 DMA engine 完成由环境补齐。
7. 内置 DMA 是当前模板唯一使用 `ISR.DONES` 的完成中断路径。

AXI burst 切分不拆分 SPI transaction。以 256 字节 payload 为例，内部 DMA 发起 4 笔 16-beat AXI burst，SPI 侧保持一组连续的 opcode、地址和数据。

## Log Verbosity

- `UVM_LOW` 只放日常必须看到的高层事件。对 WREN/program/read 这类完整 flash interaction，低冗余打印 `transfer_req.sprint()`，包内包含 opcode、payload command、address、data length、data preview、mode、CS、lane、speed、dummy 等字段；不要再用手写字符串重复打印同一组字段。
- `UVM_HIGH` 放一次 transfer 内的执行摘要：PIO DR0 stream preview、CS 选择/释放、FIFO prefill/remaining、SR completion 等待、DMA buffer 汇总、scoreboard 记录摘要。
- `UVM_DEBUG` 打印排障细节：寄存器 raw 值、NDF/BAUDR 推导中间值、寄存器配置步骤、FIFO 状态轮询、逐 byte DR0 写读、CPU DMA buffer word、scoreboard byte 比较。
- timeout 报错必须包含 `waiting_for`。中断等待写明 top `intr` 和预期来源；`SR` 轮询写明目标条件和最后一次 `SR` 原始值及字段。

## Flash Type Boundary

默认 `flash_read` / `flash_write` 是 NOR-like 便捷 flow，不代表控制器 agent 固定绑定 NOR。NAND page/cache、XIP、厂商 feature、无地址或特殊地址形态命令应新增 `model/flash_command` 指令包，并按需要新增专用 flow/kit shortcut；基础 transfer 不应强制所有 `FLASH_SPI` 都有 3/4-byte address。

## Enhanced SPI Instruction Register

`SPIDR.SPI_INST` is a 16-bit instruction container used whenever `spi_ctrlr0_en=1` or `write_internal_dma_regs=1`. Current flash commands use `inst_bytes == 1`, so the builder writes `{8'h00, opcode}` and relies on `SPI_CTRLR0.INST_L` to select an 8-bit instruction. `SPIAR.SDAR` receives the current 32-bit device address under the same combined condition.

## Speed Test

`speed_test` 按 Python `max_speed_multiplier` 顺序运行 `speed_1x`、`speed_2x`、`speed_4x`。每种倍速调用完整 `rw_test`，使用独立地址窗口 `base_address + mode_index * data_length`，避免重复 program 同一 NOR 地址。任一倍速失败后立即停止，不再运行后续测试。该测试固定使用 hardware CS，DMA 关闭。

## DMA Test

`dma_test` 仅在 Python `internal_dma` 或 `external_dma` 开启时生成并进入 filelist。每次只按 `speed_multiplier` 运行一次完整 `rw_test`，默认 1x，并强制 `use_dma=1`。内部 DMA 只通过 CPU callback 写 program payload，并从 AXI destination buffer 回读实际数据；read 启动前不写 AXI buffer 或 `DR0`。外部 DMA 在控制器选择 CS 前通过 `start_external_dma(transfer_req)` 完成配置与 arm，在控制器完成后通过 `finish_external_dma(transfer_req, read_data, ok)` 等待 DMA 并返回 DUT 实际读数据。无 DMA 配置不生成该类、kit 入口或 filelist 条目。
