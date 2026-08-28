# Xfer Flow

## Base

| 字段 | 作用 |
| --- | --- |
| `addr` | CMD17/18/24/25 或 CMD53 的地址来源 |
| `count` | block 数 |
| `size` | 每个 block 的字节数 |
| `len` | 总字节数，约束为 `count * size` |
| `dma_enable` / `dma_sel` | DMA 使能和类型；仅 `enable_dma: true` 时生成 |
| `adma_des` | ADMA 描述符数据；仅 `enable_dma: true` 时生成 |
| `abort` | 是否走 abort 场景 |
| `data_xfer_dir` | `XFER_READ` 或 `XFER_WRITE` |
| `function_number` | SDIO function number，默认 1 |
| `is_ddr` | eMMC/SD DDR 传输标记 |

公共流程：

1. `enable_dma: true`、DMA 启用且类型为 ADMA2/ADMA2_3 时，先通过 `cpu_config_operation_seq` 写入 ADMA 描述符。
2. 设置 block length。
3. 执行具体读写命令。
4. 按 `abort` 条件执行停止动作。

关键约束：

- `len == count * size`。
- SDIO 地址低 2 bit 为 0，`function_number` 在 1 到 7。
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
3. 按 `blocking` 决定 host 从 buffer 取数的时机。
4. 把 command response 的 `data` 保存到 `rdata`。

SDIO 流程：

1. 通过 CMD53 执行读。
2. 把 command response 的 `data` 保存到 `rdata`。

普通 read：

- `blocking == 0`。
- 每个 block 都先等一次 `BUF_RD_READY`，然后立刻读走一个 block。
- MSHC 从 `BUF_DATA_R` 读取。
- mobile_storage 从 `default_map.get_base_addr() + 0x200` 的 FIFO 窗口前门读取 32-bit word。
- mobile_storage 读命令前开启读 FIFO 保护，阈值按当前 block size 配置。
- 所有 block 读走后再等 `XFER_COMPLETE`。

Blocked read：

- `blocking == 1`。
- 不逐块等待 `BUF_RD_READY`。
- 先等 `XFER_COMPLETE`，再连续读取 `block_count` 个 block。
- 仅用于需要延迟取数的专门场景；普通读写测试不要默认使用。

eMMC/SD read 不支持 abort，约束 `abort == 0`。

### mobile_storage 非 DMA FIFO read

- 块级唤醒仍使用 `BUF_RD_READY`。
- 每个 word 读取前检查 `STATUS_R[2] == 0`。
- FIFO 非空后读取 `default_map.get_base_addr() + 0x200` 的 FIFO 窗口。
- 轮询期间检查 `RINTSTS_R[11]`，出现 FIFO 下溢或上溢时 fatal。

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

非 DMA 写：

- MSHC 写 `BUF_DATA_R`。
- mobile_storage 在命令发出前写 `default_map.get_base_addr() + 0x200` 的 FIFO 窗口，每 4 字节按小端组一个 word，前门 CPU 写；不等待 `CMD_COMPLETE` 后再写。

## DMA

Python 配置 `enable_dma` 默认关闭。关闭时不生成 DMA enum、DMA request 字段、ADMA descriptor、DMA interrupt/error 处理和 kit `use_dma` 参数。

DMA 传输由读写命令触发，flow 只负责准备描述符和 request 字段。

| 条件 | 行为 |
| --- | --- |
| `dma_enable == 0` | 不写 ADMA 描述符 |
| `dma_sel` 不是 ADMA2/ADMA2_3 | 不写 ADMA 描述符 |
| `dma_enable == 1` 且 ADMA2/ADMA2_3 | 用 `cpu_config_operation_seq` 后门写描述符，命令 request 携带 `dma_enable`、`dma_sel` |

ADMA 模式下，命令寄存器使用描述符地址 `adma_des.cmd_addr`；SDMA 模式下，命令寄存器使用数据地址 `addr`。
`mobile_storage` 的 DMA 模式走 IDMAC 描述符链表：`DBADDR_R` 写 `adma_des.cmd_addr`，真实数据 buffer 地址写在描述符 `real_addr` 中，写完 `DBADDR_R` 后向 `PLDMND_R` 写 `32'h1` 触发 DMA；`0x84` 是 `PLDMND_R` 地址。

DMA 数据 buffer 也通过 `cpu_config_operation_seq` 后门访问。普通 kit CPU 读写、mobile_storage 非 DMA FIFO 访问默认前门。

读写流程不自己搬 DUT 数据。DUT 数据搬运由 CPU 访问或 DMA 决定，scoreboard 只接收最终期望和实际数据。
