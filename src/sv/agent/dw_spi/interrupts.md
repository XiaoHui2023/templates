# Interrupt And Completion

## 结论

默认 transfer 完成方式是 `PREFER_INTERRUPT_COMPLETION`：如果 top interface 的 `intr` 已连接，则等待 `intr` 并读取 `ISR.DONES` 确认本次 SSI 总线完成；如果 `intr` 未连接，则退回轮询 `SR.TFE == 1 && SR.BUSY == 0`。

`INTERRUPT_COMPLETION` 是强制中断模式：必须等待 top interface 的 `intr` 拉高，然后读取 `ISR.DONES` 确认完成。该模式要求环境确认 `ISR.DONES` 或等价完成事件会路由到顶层 `intr`。

`POLLING_COMPLETION` 是强制轮询模式，只在中断不可用、专项对比或轮询效率显著更高时使用。

## IMR 的边界

`IMR` 控制 FIFO 和错误类中断 mask，不是默认完成条件。

| Field | 用途 | 不要误用为 |
| --- | --- | --- |
| `TXEIM` | TX FIFO empty interrupt mask | TX FIFO not empty 或 transfer done |
| `RXFIM` | RX FIFO full threshold interrupt mask | read complete |
| `TXOIM` | TX overflow interrupt mask | normal completion |
| `RXUIM` | RX underflow interrupt mask | normal completion |
| `RXOIM` | RX overflow interrupt mask | normal completion |
| `MSTIM` | multi-master contention interrupt mask | normal completion |

模板默认把这些 mask field 约束为 0，避免 FIFO 阈值事件误触发顶层 `intr` 后被当成事务完成。需要专门验证 FIFO/error interrupt 时，可以在 case 约束中覆盖对应 field，但这不改变 transfer completion 优先使用完成中断的原则。

## PIO 传输完成

PIO 写路径：

1. 配置寄存器并使能控制器。
2. 硬件 CS 使用 `SER`；软件 CS 只在 `SOFTWARE_CS` 时调用 callback。
3. 构造 DR byte stream：flash command/address 加可选 payload。
4. 每个 byte 等待 `SR.TFNF` 后写 `DR`。
5. 按 completion mode 等待完成。
6. 写传输只把 payload 作为 flash memory expected data 送入 scoreboard。

PIO 读路径：

1. 配置寄存器并使能控制器。
2. 写入 read command/address 的 DR stream。
3. 每个 actual byte 等待 `SR.RFNE` 后从 `DR` 读出。
4. 按 completion mode 等待总线收尾。
5. flow/test 把 actual read data 送入 scoreboard 比较。

读路径先 drain RX FIFO，再等待最终 idle/DONE，避免 RX FIFO 因等待不相关中断而溢出。

## DMA 传输完成

内部 DMA 写：

1. transfer 启动前，通过 callback `cpu_write()` 把 payload 写入 `axi_addr` 指定的系统内存 buffer。
2. 配置 `DMACR.IDMAE/AINC`、方向握手位和 `AXIAWLEN/AXIARLEN/SPIDR/SPIAR/AXIAR0`。
3. 等待 completion。
4. 将 payload 记录为 scoreboard expected data。

内部 DMA 读：

1. 配置内部 DMA 和目标 AXI buffer。
2. 等待 completion。
3. 通过 callback `cpu_read()` 从 `axi_addr` 读出 actual data。
4. flow/test 把 actual data 送入 scoreboard。

外部 DMA 只生成 `DMACR.RDMAE/TDMAE` 和 threshold 配置，外部 DMA engine 的启动、完成与 buffer 管理由环境补齐。

## 超时

`configuration.interrupt_timeout_ssi_clk_cycles` 是每次 transfer 推导出来的完成等待上限。推导输入包括 command/address/dummy/data 串行周期、`BAUDR`、FIFO 深度、margin 和 extra cycles。

使用 `PREFER_INTERRUPT_COMPLETION` 或 `INTERRUPT_COMPLETION` 时，这个字段作为 `intr` 等待上限；退回或强制使用 `POLLING_COMPLETION` 时，它作为 `SR.TFE && !SR.BUSY` 的轮询上限。

`SR.TFNF` 和 `SR.RFNE` 使用更短的 `settings.fifo_status_timeout_ssi_clk_cycles`，不复用完整 transfer 的完成超时。
