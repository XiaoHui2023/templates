# dma_engine

`dma_engine` 是内置 DMA mover，用于 transfer operation 的 DMA 模式。

它不配置寄存器。sequence 层先把 operation 请求里的 DMA 意图转换成 register `configuration`，再由 `core/register_access.sv` 写入 `DMACR`、`DMATDLR`、`DMARDLR`、`AXIAWLEN`、`AXIARLEN`、`SPIDR`、`SPIAR`、`AXIAR0`。

## 输入

| 项 | 说明 |
| --- | --- |
| `scoreboard` | flash/model memory mirror 句柄 |
| `payload` | 带地址和 byte queue 的通用传输数据包 |
| `use_dma` | 调用侧确认本次走 DMA mover |

## 行为

`move_payload(req, read_data)` 只在 `req.use_dma == 1` 时调用。

- 写传输：把 payload 数据写入 scoreboard/mem mirror。
- 读传输：从 scoreboard/mem mirror 读出数据，写回 payload，并返回 `read_data`。

这个类表示“由 DMA 搬运 payload”的内置路径。它不暴露通用 DMA API，不做寄存器读写，不处理 chip-select。
