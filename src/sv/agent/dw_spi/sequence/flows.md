# Sequence Flows

`sequence` 目录承载执行流程。`operation` 是具体动作，`flow` 组合多个 operation，`test` 组合可复用场景。sequencer 只保存句柄和 callback wrapper；kit_sequencer 只提供快捷启动入口。

## Clock Check

1. `check_clock_seq` 从 `p_sequencer.settings.vif` 获取 top interface。
2. 检查 `hclk` 和 `ssi_clk` 是否连接；X/Z 视为未连接。
3. 已连接且 req 要求检查时，采样一个完整周期并计算整数 Hz。
4. 与各自最低频率比较，默认最低 24 MHz，默认容差 1%。
5. 不检查 `sclk_out`，也不检查 `hclk` 与 `ssi_clk` 的频率关系。

`ssi_clk` 是控制器输入参考时钟。`sclk_out` 由 register configuration 阶段按 `BAUDR` 公式推导。

## Init Registers

1. `init_registers_seq` 接收一个 `transfer_req`。
2. `register_config_builder` 根据 transfer req 和 settings 生成 `configuration`。
3. builder 测量 `ssi_clk`，根据 `target_sclk_hz` 计算偶数 `BAUDR`。
4. builder 根据 `payload_bytes * 8 / data_frame_bits` 向上取整计算 DFS frame 数，并推导 `CTRLR1.NDF`。
5. `register_access` 实例化后注入 settings 和 `report_context = p_sequencer`。
6. `register_access.apply_configuration()` 按 FIELD 写 regmodel。

寄存器配置不通过 sequencer 函数完成，不通过 callback 完成，也不在 core 里引用 operation req。

## Primitive Transfer

1. `transfer_seq` 检查 req、payload、scoreboard。
2. 生成并应用本次寄存器 `configuration`。
3. 按 `cs_control_mode` 处理片选：`HARDWARE_CS` 使用 `SER`，`SOFTWARE_CS` 调用 `p_sequencer.activate_chip_select(cs_id)`。
4. 内置 DMA 写 transfer 在启动前通过 callback `cpu_write()` 把 payload 写入 `axi_addr` 指定的系统内存 buffer。
5. 非 DMA PIO 构造 DR byte stream：flash 协议包含 opcode、big-endian 地址字节；写传输追加 payload。随后等待 `SR.TFNF` 并逐 byte 写 `DR`。
6. PIO 读传输等待 `SR.RFNE` 并从 `DR` 读回 actual byte；内置 DMA 读传输在 completion 后通过 callback `cpu_read()` 从 `axi_addr` 读回 actual byte。
7. 按 `configuration.completion_mode` 等待 completion。
8. `SOFTWARE_CS` 调用 `p_sequencer.release_chip_select(cs_id)`；`HARDWARE_CS` 不调用片选 callback。
9. 写入 rsp，包括 `ok` 和实际读回数据。

## Completion Rule

| Mode | 行为 |
| --- | --- |
| `PREFER_INTERRUPT_COMPLETION` | 内置 DMA 且 `intr` 已连接时，等待 top `intr` 并检查 `ISR.DONES`；非内置 DMA 或 `intr` 未连接时，轮询 `SR.TFE && !SR.BUSY`。 |
| `INTERRUPT_COMPLETION` | 只允许内置 DMA。非内置 DMA 使用该模式会 fatal，避免误等不会来的 `ISR.DONES`。 |
| `POLLING_COMPLETION` | 强制轮询 `SR.TFE && !SR.BUSY`。 |

非 DMA PIO 不使用 `ISR.DONES`。如果以后要用中断降低 PIO CPU 占用，需要实现 FIFO/error interrupt 驱动的 PIO 状态机；不能把 `TXEIM/RXFIM` 或 `ISR.DONES` 当普通完成中断。

## Flash Read

1. 未携带 configuration 时创建 `host_configuration` 并 randomize。
2. 创建 operation transfer req 和 `uvm_tlm_generic_payload`。
3. payload command 设为 `UVM_TLM_READ_COMMAND`，address 为 flash 地址，data length 为读取长度。
4. 协议设为 `FLASH_SPI`，transfer mode 设为 `RX_ONLY`，让 enhanced 模式下 `SPI_CTRLR0.WAIT_CYCLES` 生效。
5. opcode 映射：1x standard `8'h03`，1x enhanced `8'h0B`，2x `8'hBB`，4x `8'hEB`。
6. 启动 `transfer_seq`。
7. flow sequence 保存 transfer rsp 的 `read_data`，并调用 scoreboard 比较 actual read data。

地址是 32 bit flash/model 地址，不是寄存器地址。

## Flash Write

1. 未携带 configuration 时创建 `host_configuration` 并 randomize。
2. 启动 write-enable transfer：opcode `8'h06`，`TX_ONLY`，不使用 DMA。payload 长度为 0，但 PIO DR stream 仍包含 1 byte opcode。
3. write-enable 成功后启动 program transfer：1x `8'h02`，2x `8'hA2`，4x `8'h32`，`TX_AND_RX`。
4. payload command 为 `UVM_TLM_WRITE_COMMAND`，address 为 flash 地址，data 为写入 byte 队列。
5. flow sequence 记录 `ok` 和 `bytes_written`。

当前模板暂不实现 flash erase `8'hC7`、status poll `8'h05`、QE/WRSR 和 256B 分页写限制。

## RW Test

读写测试顺序是写后读。

1. 未携带 configuration 时创建 `host_configuration` 并 randomize。
2. `write_data` 为空时随机生成一段数据，长度来自 Python `default_rw_data_bytes`，默认 256 byte。
3. 启动 `flash_write`。
4. 启动同地址同长度的 `flash_read`。
5. 调用 `scoreboard.check_actual_read(address, read_data, "rw_readback_actual")`，比较对象是真实读传输从 `DR` 或 DMA buffer 读回的 actual data。

## DMA Transfer

1. Python 通过 `internal_dma` / `external_dma` 选择生成内置 DMA、外部 DMA 或无 DMA，二者不能同时开启。
2. 无 DMA 时不生成 `use_dma` 和 DMA 寄存器配置。
3. 内置 DMA 时，per-transfer configuration 可设置 `use_dma`、`awlen`、`arlen`、`axi_addr`；builder 转换成 `DMACR.RDMAE/TDMAE/IDMAE/AINC`、DMA threshold、`AXIAWLEN.AWLEN = awlen << 8`、`AXIARLEN.ARLEN = arlen << 8`、`SPIDR.SPI_INST`、`SPIAR.SDAR`、`AXIAR0.AXIAR0`。
4. 外部 DMA 时，只配置 `DMACR.RDMAE/TDMAE` 和 DMA threshold；外部 DMA engine 完成由环境补齐。
5. 内置 DMA 是当前模板唯一使用 `ISR.DONES` 的完成中断路径。

## Log Verbosity

- `UVM_LOW` 说明流程正在做什么、正在等待什么、完成了什么。
- `UVM_DEBUG` 打印寄存器字段值、推导中间值、FIFO 状态轮询、DR byte、CPU DMA buffer word、scoreboard byte 比较。
- timeout 报错必须包含 `waiting_for`。中断等待写明 top `intr` 和预期来源；`SR` 轮询写明目标条件和最后一次 `SR` 原始值及字段。
