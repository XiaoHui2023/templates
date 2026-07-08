# Sequence Flows

`sequence` 目录承载执行流程。`operation` 是具体动作，`flow` 组合多个 operation，`test` 组合可复用场景。sequencer 只保存句柄和 callback wrapper，kit_sequencer 只提供快捷启动入口。

## Clock Check

1. `check_clock_seq` 从 `p_sequencer.settings.vif` 获取 top interface。
2. 检查 `hclk` 和 `ssi_clk` 是否连接；X/Z 视为未连接。
3. 已连接且 req 要求检查时，采样一个完整周期并计算整数 Hz。
4. 与各自最低频率比较，默认最低频率为 24 MHz，默认容差为 1%。
5. 不检查 `sclk_out`，也不检查 `hclk` 与 `ssi_clk` 的频率关系。

`ssi_clk` 是控制器输入参考时钟。`sclk_out` 由 register configuration 阶段按 `BAUDR` 公式推导。

## Init Registers

1. `init_registers_seq` 接收一个 `transfer_req`。
2. `register_config_builder` 根据 transfer req 和 settings 生成 `configuration`。
3. builder 测量 `ssi_clk`，根据 `target_sclk_hz` 计算偶数 `BAUDR`。
4. builder 根据 `payload_bytes * 8 / data_frame_bits` 向上取整计算 DFS frame 数，并推导 `CTRLR1.NDF`。
5. `register_access` 实例化后注入 settings。
6. `register_access.apply_configuration()` 按 FIELD 写 regmodel。

寄存器配置不通过 sequencer 函数完成，不通过 callback 完成，也不在 core 里引用 operation req。

## Primitive Transfer

1. `transfer_seq` 检查 req、payload、scoreboard。
2. 生成并应用本次寄存器 `configuration`。
3. 调用 `p_sequencer.activate_chip_select(cs_id)`。
4. `use_dma == 1` 时，实例化 `dma_engine` 并搬运 payload。
5. 等待 top interface 的 `intr` 断言，超时按 `ssi_clk` 周期计数。
6. `use_dma == 0` 时，调用 `scoreboard.apply_payload()` 建模 PIO 数据效果。
7. 调用 `p_sequencer.release_chip_select(cs_id)`。
8. 写入 rsp，包括 `ok` 和读数据。

callback 只注入 chip-select 行为。寄存器读写、scoreboard 比较、DMA 搬运都不放进 callback。

## Flash Read

1. req 未携带 configuration 时创建 `host_configuration` 并 randomize。
2. 创建 operation transfer req 和 `uvm_tlm_generic_payload`。
3. payload command 设为 `UVM_TLM_READ_COMMAND`，address 为 flash 地址，data length 为读长度。
4. 协议设为 `FLASH_SPI`，transfer mode 设为 `EEPROM_READ`。
5. read opcode 根据倍速选择：1 倍速 standard 使用 `8'h03`，1 倍速 enhanced 使用 `8'h0B`，2 倍速使用 `8'h3B`，4 倍速使用 `8'hEB`，8 倍速使用 `8'hEC`。
6. 从 configuration 传播 io lanes、倍速、SPI mode、data frame bits、CS、地址字节数、dummy cycles、DMA 开关。
7. 启动 `transfer_seq`。
8. flow rsp 保存 transfer rsp 的 `read_data`。

地址是 32 bit flash/model 地址，不是寄存器地址。

## Flash Write

1. req 未携带 configuration 时创建 `host_configuration` 并 randomize。
2. 启动 write-enable transfer：opcode `8'h06`，`TX_ONLY`，不使用 DMA。
3. write-enable 成功后启动 page/program 风格写 transfer：1/2 倍速 opcode 使用 `8'h02`，4 倍速使用 `8'h32`，8 倍速使用 `8'h12`，`TX_ONLY`。
4. 写 transfer 的 payload command 为 `UVM_TLM_WRITE_COMMAND`，address 为 flash 地址，data 为写入 byte 队列。
5. 写 transfer 按 configuration 传播 io lanes、倍速、SPI mode、data frame bits、CS、地址字节数、DMA 开关。
6. flow rsp 记录 `ok` 和 `bytes_written`。

当前模板不建模页大小、擦除值和擦除流程。

## RW Test

1. req 未携带 configuration 时创建 `host_configuration` 并 randomize。
2. `write_data` 为空时随机生成一段数据，长度来自 Python `default_rw_data_bytes`，默认 256 byte。
3. 启动 `flash_write`。
4. 启动同地址同长度的 `flash_read`。
5. 调用 `scoreboard.compare_actual(address, write_data, "model_readback")`。

读写测试顺序是写后读。读回数据不从 kit API 返回，test sequence 负责把数据交给 scoreboard 自动校验。

## DMA Transfer

1. per-transfer configuration 设置 `use_dma`。
2. `register_config_builder` 把 DMA 意图转换成 `DMACR.IDMAE/AINC`、DMA threshold、`AXIAWLEN.AWLEN`、`AXIARLEN.ARLEN`、`SPIDR.SPI_INST`、`SPIAR.SDAR`、`AXIAR0.AXIAR0`。
3. `SPIDR.SPI_INST` 来自 transfer opcode，`SPIAR.SDAR` 来自 payload address，`AXIAR0.AXIAR0` 来自 per-transfer `axi_addr`。
4. `register_access` 写 `DMACR`、`DMATDLR`、`DMARDLR`、`AXIAWLEN`、`AXIARLEN`、`SPIDR`、`SPIAR`、`AXIAR0`。
5. `transfer_seq` 在 chip-select 打开后调用 `dma_engine.move_payload()`。
6. DMA mover 只搬运 payload 与 scoreboard mirror，不配置寄存器，不处理 CS。

DMA 是单次传输模式，不是 sequencer 快捷函数。

## Slave Mode

`slave_configuration` 约束 `host_mode == SLAVE`。从机模式仍通过相同的 transfer req 传播协议形态；寄存器配置阶段写 `CTRLR0.SSI_IS_MST = 0`。

从机侧真实外部时序、外部 master 驱动、CS 极性和数据采集方式由环境或 callback/接口实现补齐。

## Interrupt Timeout

`transfer_seq` 等待 `intr` 时必须有超时保护。

- 正常路径按 `settings.interrupt_timeout_ssi_clk_cycles` 统计 `ssi_clk` 周期。
- 防卡死路径按 `settings.min_ssi_clk_hz` 和 `settings.clock_check_tolerance_ppm` 推导仿真时间上限。即使 `ssi_clk` 停住，等待也会返回超时并 `uvm_fatal`。
