# DMA Buffer Access

## Data Integrity

DMA completion alone does not prove data integrity. The DMA test reuses `rw_test`: program data is recorded as expected only after successful completion, then a DMA read obtains actual bytes from the destination buffer and scoreboard checks both the requested length and every byte. An empty callback result with `ok=1` is therefore still an error.

`core/dma_engine.sv` 不进入 generated `all.f`。内置 DMA 数据搬运通过 sequencer callback 注入 CPU 32-bit 读写，由外部 CPU/AXI 模型在 `axi_addr` 指定的系统内存 buffer 上完成。

sequence 层先把 operation 请求里的 DMA 意图转换成 register `configuration`，再由 `core/register_access.sv` 写入 `DMACR`、`DMATDLR`、`DMARDLR`、`AXIAWLEN`、`AXIARLEN`、`AXIAR0`。`SPIDR/SPIAR` 在 `spi_ctrlr0_en=1` 或 `write_internal_dma_regs=1` 时写入。

`AXIAWLEN.AWLEN` 与 `AXIARLEN.ARLEN` 仅低四位有效，表示允许的单笔最大 burst beat 数减一。内部 DMA 固定设置两者为 15，builder 直接写四位 req 值，不做位移。软件不按本次数据量计算 LEN；控制器内部 DMA 根据总搬运量自动安排 AXI burst，SPI transaction 不拆分。

## Callback Contract

| Task | 用途 |
| --- | --- |
| `cpu_write(addr, data, path)` | 内部 DMA 启动前写 AXI source buffer；写命令放 payload，读命令放控制项 |
| `cpu_read(addr, data, path)` | DMA 读传输完成后读 AXI destination buffer |

`path` 是 `uvm_path_e`。内置 DMA buffer 准备和回读固定使用 `UVM_BACKDOOR`，与 `dw_emmc` 的 DMA buffer/descriptor 访问习惯一致。`UVM_FRONTDOOR` 预留给普通 CPU 总线访问扩展，不用于当前内置 DMA 快速 buffer 搬运。

## 行为

内置 DMA 写传输：

1. 在配置启动控制器前，把 payload byte 按 32-bit little-endian word 写入 `axi_addr`。
2. 每个 word 调用 `p_sequencer.cpu_write(addr, word, UVM_BACKDOOR)`。
3. 传输完成后把 payload 记录到 scoreboard expected mirror。

内置 DMA 读传输：

1. 根据指令包构造 opcode/address 控制项；standard 地址按 byte 展开，enhanced 地址使用一个 32-bit item。
2. 每个控制项调用 `p_sequencer.cpu_write(addr, word, UVM_BACKDOOR)` 写入 `axi_addr`，内部 DMA 引擎从 AXI source buffer 取数；不写 `DR0`。
3. `ARLEN/AWLEN` 均固定为 15，控制器根据控制项和接收 payload 的总量自动安排 burst。
4. 控制器完成 DMA 后，从 `axi_addr` 按 32-bit little-endian word 读回数据。
5. 每个 word 调用 `p_sequencer.cpu_read(addr, word, UVM_BACKDOOR)`。
6. 读回 byte 作为 actual read data 交给 flow/test 和 scoreboard 比较。

CPU 读写 callback 不暴露通用寄存器 API，不处理 chip-select。

## Enhanced SPI Instruction Packing

`SPIDR.SPI_INST` uses a 16-bit instruction container. DWC SSI RTL consumes a 1-byte SPI flash opcode from the low byte, so pack it as `{8'h00, opcode}`. The actual 8-bit instruction length is expressed by `SPI_CTRLR0.INST_L`.
