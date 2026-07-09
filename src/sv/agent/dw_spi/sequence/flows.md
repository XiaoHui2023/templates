# Sequence Flows

`sequence` 目录承载执行流程。`operation` 是具体动作，`flow` 组合多个 operation，`test` 组合可复用场景。sequencer 只保存句柄和 callback wrapper，kit_sequencer 只提供快捷启动入口。

## Clock Check

1. `check_clock_seq` 从 `p_sequencer.settings.vif` 获取 top interface。
2. 检查 `hclk` 和 `ssi_clk` 是否连接；X/Z 视为未连接。
3. 已连接且 req 要求检查时，采样一个完整周期并计算整数 Hz。
4. 与各自最低频率比较，默认最低频率为 24 MHz，默认容差为 1%。
5. 不检查 `sclk_out`，也不检查 `hclk` 与 `ssi_clk` 的频率关系。

`ssi_clk` 是控制器输入参考时钟。`sclk_out` 由 register configuration 阶段按 `BAUDR` 公式推导。

`check_clock_seq` 使用 `UVM_LOW` 打印检查结果。时钟已连接且检查通过时打印测得频率、最低频率和容差；时钟未连接时打印跳过原因。

## Init Registers

1. `init_registers_seq` 接收一个 `transfer_req`。
2. `register_config_builder` 根据 transfer req 和 settings 生成 `configuration`。
3. builder 测量 `ssi_clk`，根据 `target_sclk_hz` 计算偶数 `BAUDR`。
4. builder 根据 `payload_bytes * 8 / data_frame_bits` 向上取整计算 DFS frame 数，并推导 `CTRLR1.NDF`。
5. `register_access` 实例化后注入 settings。
6. `register_access.apply_configuration()` 按 FIELD 写 regmodel。

寄存器配置不通过 sequencer 函数完成，不通过 callback 完成，也不在 core 里引用 operation req。

`register_config_builder` 使用 `UVM_LOW` 打印本次推导出的 `ssi_clk`、目标 `sclk`、`BAUDR`、DFS 位宽、`NDF`、`SPI_FRF` 和 `SER`。

## Primitive Transfer

1. `transfer_seq` 检查 req、payload、scoreboard。
2. 生成并应用本次寄存器 `configuration`。
3. 调用 `p_sequencer.activate_chip_select(cs_id)`。
4. 内部 DMA 且 `use_dma == 1` 的写传输，在寄存器配置/启动前通过 callback `cpu_write()` 把 payload 写入 `axi_addr` 指定的系统内存 buffer。
5. 等待 top interface 的 `intr` 断言，超时按 `ssi_clk` 周期计数。
6. `use_dma == 0` 时，PIO 写传输先等待 `SR.TFNF` 再把 payload byte 写入 `DR`。
7. 等待 `intr` 后，PIO 读传输等待 `SR.RFNE` 并从 `DR` 读回 actual byte；内部 DMA 读传输通过 callback `cpu_read()` 从 `axi_addr` 读回 actual byte；写传输把已生效 payload 记录为 scoreboard 期望值。
8. 调用 `p_sequencer.release_chip_select(cs_id)`。
9. 写入 rsp，包括 `ok` 和从 `DR` 读回的数据。

callback 注入 chip-select 行为和 CPU 32-bit 读写。寄存器配置、scoreboard 比较和协议编排不放进 callback。

`transfer_seq` 使用 `UVM_LOW` 打印 primitive transfer 的开始和结束摘要，包括协议、传输模式、opcode、地址、长度、CS、线数、倍速、DFS 位宽、DMA 开关和读回字节数。

## Flash Read

1. sequence 未携带 configuration 时创建 `host_configuration` 并 randomize。
2. 创建 operation transfer req 和 `uvm_tlm_generic_payload`。
3. payload command 设为 `UVM_TLM_READ_COMMAND`，address 为 flash 地址，data length 为读长度。
4. 协议设为 `FLASH_SPI`，transfer mode 设为 `RX_ONLY`，使增强模式下 `SPI_CTRLR0.WAIT_CYCLES` 生效。
5. read opcode 根据倍速选择：1 倍速 standard 使用 `8'h03`，1 倍速 enhanced 使用 `8'h0B`，2 倍速使用 `8'hBB`，4 倍速使用 `8'hEB`。
6. 从 configuration 传播 io lanes、倍速、SPI mode、data frame bits、CS、地址字节数、dummy cycles、DMA 开关。
7. 启动 `transfer_seq`。
8. flow sequence 保存 transfer rsp 的 `read_data` 到自身返回字段，并调用 scoreboard 把 actual read data 与 mirror 比较。

地址是 32 bit flash/model 地址，不是寄存器地址。

`flash_read_seq` 使用 `UVM_LOW` 打印开始和结束摘要，包括地址、长度、线数、倍速、frame mode、DMA 开关、opcode 和接收字节数。

## Flash Write

1. sequence 未携带 configuration 时创建 `host_configuration` 并 randomize。
2. 启动 write-enable transfer：opcode `8'h06`，`TX_ONLY`，不使用 DMA。
3. write-enable 成功后启动 page/program 风格写 transfer：1 倍速 opcode 使用 `8'h02`，2 倍速使用 `8'hA2`，4 倍速使用 `8'h32`，`TX_AND_RX`。
4. 写 transfer 的 payload command 为 `UVM_TLM_WRITE_COMMAND`，address 为 flash 地址，data 为写入 byte 队列。
5. 写 transfer 按 configuration 传播 io lanes、倍速、SPI mode、data frame bits、CS、地址字节数、DMA 开关。
6. flow sequence 在自身字段记录 `ok` 和 `bytes_written`。

当前模板暂不实现 flash erase `8'hC7`、status poll `8'h05`、QE/WRSR 和 256B 分页写限制；后续加入真实 SPI-NOR 行为时必须把这些流程补进 flash write/erase flow。

`flash_write_seq` 使用 `UVM_LOW` 打印开始、write-enable 结果、chunk 写结果和最终写入字节数。

## RW Test

1. sequence 未携带 configuration 时创建 `host_configuration` 并 randomize。
2. `write_data` 为空时随机生成一段数据，长度来自 Python `default_rw_data_bytes`，默认 256 byte。
3. 启动 `flash_write`。
4. 启动同地址同长度的 `flash_read`。
5. 调用 `scoreboard.check_actual_read(address, read_data, "rw_readback_actual")`，比较对象是读传输从 `DR` 读回的 actual data。

读写测试顺序是写后读。读回数据不从 kit API 返回，test sequence 负责把数据交给 scoreboard 自动校验。

`rw_test_seq` 使用 `UVM_LOW` 打印测试开始和结束摘要，包括地址、数据长度、线数、倍速、frame mode、DMA 开关、读回字节数和最终 `ok`。

## DMA Transfer

1. Python 通过 `internal_dma` / `external_dma` 选择生成内部 DMA、外部 DMA 或无 DMA，二者不能同时开启。
2. 无 DMA 时不生成 `use_dma` 和 DMA 寄存器配置。
3. 内部 DMA 时，per-transfer configuration 可设置 `use_dma`、`awlen`、`arlen`、`axi_addr`；`register_config_builder` 转换成 `DMACR.RDMAE/TDMAE/IDMAE/AINC`、DMA threshold、`AXIAWLEN.AWLEN = awlen << 8`、`AXIARLEN.ARLEN = arlen << 8`、`SPIDR.SPI_INST`、`SPIAR.SDAR`、`AXIAR0.AXIAR0`。
4. 外部 DMA 时，per-transfer configuration 只设置 `use_dma`；`register_config_builder` 根据传输方向配置 `DMACR.RDMAE/TDMAE` 和 DMA threshold。
5. 内部 DMA 写传输启动前调用 `cpu_write()` 准备 AXI source buffer；内部 DMA 读传输完成后调用 `cpu_read()` 读取 AXI destination buffer。外部 DMA 不使用内置 CPU buffer mover。

DMA 是单次传输模式，不是 sequencer 快捷函数。

## Slave Mode

`slave_configuration` 约束 `host_mode == SLAVE`。从机模式仍通过相同的 transfer req 传播协议形态；寄存器配置阶段写 `CTRLR0.SSI_IS_MST = 0`。

从机侧真实外部时序、外部 master 驱动、CS 极性和数据采集方式由环境或 callback/接口实现补齐。

## Interrupt Timeout

`transfer_seq` 等待 `intr` 时必须有超时保护。

- 正常路径按 `settings.interrupt_timeout_ssi_clk_cycles` 统计 `ssi_clk` 周期。
- 防卡死路径按 `settings.min_ssi_clk_hz` 和 `settings.clock_check_tolerance_ppm` 推导仿真时间上限。即使 `ssi_clk` 停住，等待也会返回超时并 `uvm_fatal`。
