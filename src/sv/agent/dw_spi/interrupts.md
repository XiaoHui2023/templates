# Interrupt And Completion

## 结论

`ISR.DONES` 不是公共 DW APB SSI 资料里的通用 PIO transfer done 中断。当前模板把它当成本地 DWC SSI/内置 DMA 扩展完成位使用：只有 `internal_dma` 生成、且本次 `use_dma == 1` 时，才允许等待 top `intr` 后读取 `ISR.DONES` 确认完成。

非 DMA PIO 不使用 `ISR.DONES`。默认 `PREFER_INTERRUPT_COMPLETION` 在非 DMA PIO 下会轮询 `SR.TFE == 1 && SR.BUSY == 0`；`INTERRUPT_COMPLETION` 如果用于非内置 DMA transfer，会直接 fatal。以后如果要降低 PIO CPU 占用，需要实现 FIFO/error interrupt 驱动的 PIO 状态机，而不是把 FIFO interrupt 或 `ISR.DONES` 当成普通完成中断。

## IMR 边界

`IMR` 控制 FIFO 和错误类中断 mask，不是默认完成条件。

| Field | 用途 | 不要误用为 |
| --- | --- | --- |
| `TXEIM` | TX FIFO empty interrupt mask | TX FIFO not empty 或 transfer done |
| `RXFIM` | RX FIFO full/threshold interrupt mask | read complete |
| `TXOIM` | TX overflow interrupt mask | normal completion |
| `RXUIM` | RX underflow interrupt mask | normal completion |
| `RXOIM` | RX overflow interrupt mask | normal completion |
| `MSTIM` | multi-master contention interrupt mask | normal completion |

模板默认把这些 mask field 约束为 0。需要专项验证 FIFO/error interrupt 时，可以在 case 约束中覆盖对应 field，但这不改变 transfer completion 的判断规则。

## PIO Completion

PIO 写流程：

1. 在 `SER=0` 时预填部分 DR stream。
2. 选中 CS。
3. 在 CS 有效期间继续写剩余 DR stream。
4. 等待 `SR.TFE && !SR.BUSY` 收尾。
5. 释放 CS。
6. 把 payload 记录为 scoreboard expected data。

PIO 读流程：

1. 在 `SER=0` 时预填 read command/address DR stream。
2. 选中 CS。
3. 用 `SR.RFNE` 从 `DR` 读回 actual data。
4. 等待 `SR.TFE && !SR.BUSY` 收尾。
5. 释放 CS。
6. flow/test 把 actual read data 送入 scoreboard 比较。

PIO 读必须先 drain RX FIFO，再等待最终 idle，避免 RX FIFO 因等待无关中断而溢出。

## Internal DMA Completion

内置 DMA 是当前模板唯一使用 `ISR.DONES` 的路径。

1. 内置 DMA transfer 启动前，通过 callback `cpu_write(addr, word, UVM_BACKDOOR)` 准备 AXI source buffer：写命令放 payload，读命令放 opcode/address 控制项；内部 DMA 读不写 `DR`。
2. 配置 `DMACR.IDMAE/AINC`、方向握手位和 `AXIAWLEN/AXIARLEN/AXIAR0`。`SPIDR/SPIAR` 在 `write_internal_dma_regs` 或 enhanced `spi_ctrlr0_en` 任一条件成立时写入。
3. 选中 CS，启动控制器内部 DMA transfer。
4. 若 `completion_mode` 是 `PREFER_INTERRUPT_COMPLETION` 且 `intr` 已连接，等待 top `intr`，再读取 `ISR.DONES`。
5. 若 `intr` 未连接，退回轮询 `SR.TFE && !SR.BUSY`。
6. 释放 CS。
7. 内置 DMA 读 transfer 在释放 CS 后，通过 callback `cpu_read(addr, word, UVM_BACKDOOR)` 从 `axi_addr` 读回 actual data；`ARLEN/AWLEN` 固定为 15，控制器根据总搬运量自动安排 AXI burst。

外部 DMA 只生成 `DMACR.RDMAE/TDMAE` 和 threshold 配置；外部 DMA engine 的启动、完成与 buffer 管理由环境补齐。当前模板不把 `ISR.DONES` 用作外部 DMA 默认完成源。

## Timeout

`configuration.interrupt_timeout_ssi_clk_cycles` 是每次 transfer 推导出的完成等待上限。中断路径用它限制 `intr` 等待；轮询路径用它限制 `SR.TFE && !SR.BUSY`。

`SR.TFNF` 和 `SR.RFNE` 使用更短的 `settings.fifo_status_timeout_ssi_clk_cycles`，不复用完整 transfer 的完成超时。

timeout 报错必须显示等待目标：

- 中断等待显示 `waiting_for=top intr asserted`、`expected_source=ISR.DONES internal DMA completion` 和 transfer 上下文。
- `SR` 轮询显示目标条件，例如 `SR.TFNF==1`、`SR.RFNE==1` 或 `SR.TFE==1 && SR.BUSY==0`，并打印最后一次 `SR` 原始值和字段。
