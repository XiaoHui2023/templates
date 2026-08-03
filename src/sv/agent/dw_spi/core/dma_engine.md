# DMA Buffer Access

`core/dma_engine.sv` 不进入 generated `all.f`。内置 DMA 数据搬运通过 sequencer callback 注入 CPU 32-bit 读写，由外部 CPU/AXI 模型在 `axi_addr` 指定的系统内存 buffer 上完成。

sequence 层先把 operation 请求里的 DMA 意图转换成 register `configuration`，再由 `core/register_access.sv` 写入 `DMACR`、`DMATDLR`、`DMARDLR`、`AXIAWLEN`、`AXIARLEN`、`SPIDR`、`SPIAR`、`AXIAR0`。

## Callback Contract

| Task | 用途 |
| --- | --- |
| `cpu_write(addr, data, path)` | DMA 写传输前写 AXI source buffer |
| `cpu_read(addr, data, path)` | DMA 读传输完成后读 AXI destination buffer |

`path` 是 `uvm_path_e`。内置 DMA buffer 准备和回读固定使用 `UVM_BACKDOOR`，与 `dw_emmc` 的 DMA buffer/descriptor 访问习惯一致。`UVM_FRONTDOOR` 预留给普通 CPU 总线访问扩展，不用于当前内置 DMA 快速 buffer 搬运。

## 行为

内置 DMA 写传输：

1. 在配置启动控制器前，把 payload byte 按 32-bit little-endian word 写入 `axi_addr`。
2. 每个 word 调用 `p_sequencer.cpu_write(addr, word, UVM_BACKDOOR)`。
3. 传输完成后把 payload 记录到 scoreboard expected mirror。

内置 DMA 读传输：

1. 控制器完成 DMA 后，从 `axi_addr` 按 32-bit little-endian word 读回数据。
2. 每个 word 调用 `p_sequencer.cpu_read(addr, word, UVM_BACKDOOR)`。
3. 读回 byte 作为 actual read data 交给 flow/test 和 scoreboard 比较。

CPU 读写 callback 不暴露通用寄存器 API，不处理 chip-select。

## SPIDR Instruction Packing

`SPIDR.SPI_INST` uses a 16-bit instruction container. A 1-byte SPI flash opcode is packed as `{opcode, 8'h00}` and the actual 8-bit instruction length is expressed by `SPI_CTRLR0.INST_L`. Do not treat the container width as `inst_bytes`, and do not low-align the opcode as `16'h00xx`.
