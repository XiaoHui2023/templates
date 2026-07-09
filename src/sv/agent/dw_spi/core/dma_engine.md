# DMA Buffer Access

`core/dma_engine.sv` 不再进入 generated `all.f`。内部 DMA 数据搬运通过 sequencer callback 注入 CPU 32-bit 读写，由外部 CPU/AXI 模型在 `axi_addr` 指定的系统内存 buffer 上完成。

sequence 层先把 operation 请求里的 DMA 意图转换成 register `configuration`，再由 `core/register_access.sv` 写入 `DMACR`、`DMATDLR`、`DMARDLR`、`AXIAWLEN`、`AXIARLEN`、`SPIDR`、`SPIAR`、`AXIAR0`。

## 输入

| 项 | 说明 |
| --- | --- |
| `cpu_write` | DMA 写传输前写 AXI source buffer |
| `cpu_read` | DMA 读传输完成后读 AXI destination buffer |
| `payload` | 带 flash 地址和 byte queue 的通用传输数据包 |
| `axi_addr` | DMA 访问系统内存的 byte 地址 |

## 行为

内部 DMA 写传输：

- 在配置/启动控制器前，把 payload byte 按 32-bit little-endian word 写入 `axi_addr`。
- 传输完成后把 payload 记录到 scoreboard expected mirror。

内部 DMA 读传输：

- 控制器完成 DMA 后，从 `axi_addr` 按 32-bit little-endian word 读回数据。
- 读回 byte 作为 actual read data 交给 flow/test 和 scoreboard 比较。

CPU 读写 callback 不暴露通用寄存器 API，不处理 chip-select。
