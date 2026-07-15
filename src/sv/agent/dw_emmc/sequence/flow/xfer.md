# Xfer Flow

## Base

| 字段 | 作用 |
| --- | --- |
| `addr` | CMD17/18/24/25 或 CMD53 的地址来源 |
| `count` | block 数 |
| `size` | 每个 block 的字节数 |
| `len` | 总字节数，约束为 `count * size` |
| `dma_enable` / `dma_sel` | DMA 使能和类型 |
| `adma_des` | ADMA 描述符数据 |
| `abort` | 是否走 abort 场景 |
| `data_xfer_dir` | `XFER_READ` 或 `XFER_WRITE` |
| `function_number` | SDIO function number，默认 1 |
| `is_ddr` | eMMC/SD DDR 传输标记 |

公共流程：

1. DMA 启用且类型为 ADMA2/ADMA2_3 时，先通过 `cpu_config_operation_seq` 写入 ADMA 描述符。
2. 设置 block length。
3. 执行具体读写命令。
4. 按 `abort` 条件执行停止动作。

关键约束：

- `len == count * size`。
- SDIO 地址 4 字节对齐，`function_number` 在 1 到 7。
- eMMC DDR/HS400 时 `size == 512`。
- SDSC 不支持多 block，`count == 1`。
- ADMA 描述符地址和数据地址不能重叠。

## Read

| 字段 | 作用 |
| --- | --- |
| `blocking` | 是否先等读传输完成，再一次性从 controller buffer 取数 |
| `rdata` | 命令 response 中返回的数据 |

eMMC/SD 流程：

1. `count > 1` 时先发 CMD23 设置 block count。
2. `count > 1` 时发 CMD18，否则发 CMD17。
3. 按 `blocking` 决定 host 侧从 buffer 取数的时机。
4. 把 command response 的 `data` 保存到 `rdata`。

SDIO 流程：

1. 通过 CMD53 执行读。
2. 把 command response 的 `data` 保存到 `rdata`。

普通 read：

- `blocking == 0`。
- 每个 block 都先等一次 `BUF_RD_READY`，然后立刻读走一个 block 的 `BUF_DATA_R`。
- 所有 block 读走后再等 `XFER_COMPLETE`。

Blocked read：

- `blocking == 1`。
- 不逐块等待 `BUF_RD_READY`。
- 先等 `XFER_COMPLETE`，再连续读取 `block_count` 个 block 的 `BUF_DATA_R`。
- 仅用于需要延迟取数的专门场景；普通读写测试不要默认使用。

eMMC/SD read 不支持 abort，约束 `abort == 0`。

## Write

| 字段 | 作用 |
| --- | --- |
| `write_protected` | 写保护场景，关闭 data present |
| `wdata` | 写入数据，长度等于 `len` |

eMMC/SD 流程：

1. `count > 1` 且非 abort 时先发 CMD23 设置 block count。
2. `count > 1` 时发 CMD25，否则发 CMD24。
3. abort 场景打开 `AUTO_CMD12_ENABLED`。
4. 写保护场景把 `data_present_sel` 置 0。

SDIO 流程：

1. 通过 CMD53 执行写。
2. `wdata` 传入 CMD53 request。

## DMA

DMA 传输由读写命令触发，flow 只负责准备描述符和 request 字段。

| 条件 | 行为 |
| --- | --- |
| `dma_enable == 0` | 不写 ADMA 描述符 |
| `dma_sel` 不是 ADMA2/ADMA2_3 | 不写 ADMA 描述符 |
| `dma_enable == 1` 且 ADMA2/ADMA2_3 | 用 `cpu_config_operation_seq` 后门写描述符，命令 request 携带 `dma_enable`、`dma_sel` |

ADMA 模式下，命令寄存器使用描述符地址 `adma_des.cmd_addr`；SDMA 模式下，命令寄存器使用数据地址 `addr`。

DMA 数据 buffer 也通过 `cpu_config_operation_seq` 后门访问。普通 kit CPU 读写默认前门访问。

读写流程不自己搬 DUT 侧数据。DUT 侧数据搬运由 CPU 访问或 DMA 决定，scoreboard 只接收最终期望和实际数据。
