# Xfer Flow

## Base

| 字段 | 作用 |
| --- | --- |
| `addr` | CMD17/18/24/25 或 CMD53 的地址来源 |
| `count` | block 数 |
| `size` | 每个 block 的字节数 |
| `len` | 总字节数，约束为 `count * size` |
| `dma_enable` / `dma_sel` | DMA 使能和类型；仅 `enable_dma: true` 时生成；mobile_storage 不使用 `dma_sel` 写寄存器 |
| `adma_des` | MSHC ADMA 描述符数据；仅 `enable_dma: true` 且 `controller_ip: mshc` 时生成 |
| `idmac_descriptor` | mobile_storage IDMAC 描述符数据；仅 `enable_dma: true` 且 `controller_ip: mobile_storage` 时生成 |
| `abort` | 提前停止传输；eMMC/SD 读不支持 |
| `data_xfer_dir` | `XFER_READ` 或 `XFER_WRITE` |
| `function_number` | SDIO function number，默认 1 |
| `is_ddr` | eMMC/SD DDR 传输标记 |

按顺序准备 DMA 描述符（启用时）、设置块长、执行读写命令，并处理提前停止。

SDIO 地址按 4 字节对齐，`function_number` 为 1 至 7；单块不写块长，提前停止时在 CMD53 后发 CMD52。eMMC DDR 或 HS400 使用 512 字节块且不发 CMD16；SDSC 只允许单块。

## Read

| 字段 | 作用 |
| --- | --- |
| `blocking` | PIO 阻塞读模式 |
| `rdata` | 命令 response 中返回的数据 |

eMMC/SD 单块读发 CMD17，多块读先发 CMD23 再发 CMD18。SDIO 发 CMD53。命令返回后把响应中的 `data` 保存到 `rdata`。

| 控制器 | `blocking == 0` | `blocking == 1` |
| --- | --- | --- |
| MSHC | 逐块等待 BRR 并从 `BUF_DATA_R` 取数，最后等 TC | 按同一顺序逐块取数，等 TC 后一次性写入响应队列 |
| mobile_storage SDIO | 逐块等待 RXDR，逐字确认 FIFO 非空后取数，最后等 DTO | 先等 DTO，再逐字确认 FIFO 非空后取数，不等待 RXDR |

DMA 读先等传输完成，再从内存取数，不使用 PIO 阻塞读模式。

mobile_storage 发读命令前按块长设置 FIFO 保护阈值。每读一个 32 位字前检查 `STATUS_R[2] == 0`，轮询期间若 `RINTSTS_R[11]` 置位则报 `UVM_FATAL`。FIFO 窗口从 `default_map.get_base_addr() + 0x200` 开始，使用前门访问。

扩展读操作时，继承实际命令类或相同的 request 特化。只改变单块搬运时重写 `read_buffer_one_block`，保留等待顺序；需要改变路径选择时才重写 `read`。用实际创建类型的 `get_type()` 注册工厂替换，并经基类句柄启动序列验证重写。

## Write

| 字段 | 作用 |
| --- | --- |
| `write_protected` | 写保护场景，关闭 data present |
| `wdata` | 写入数据，长度等于 `len` |

eMMC/SD 单块写发 CMD24，多块写发 CMD25；非 abort 的多块写先发 CMD23，abort 时启用 `AUTO_CMD12_ENABLED`。写保护时将 `data_present_sel` 置 0。SDIO 将 `wdata` 传给 CMD53。

非 DMA 写时，MSHC 写 `BUF_DATA_R`；mobile_storage 在发命令前以前门写 FIFO 窗口，每 4 字节按小端组成一个 32 位字。

## DMA

生成参数 `enable_dma` 默认关闭；未生成 DMA 时没有 `use_dma` 参数。运行时 `dma_enable == 0` 不写描述符。DMA 描述符与数据缓冲区不重叠，均通过 `cpu_config_operation_seq` 后门访问。

| 模式 | 描述符 | 命令操作使用的地址 |
| --- | --- | --- |
| MSHC SDMA | 无 | 数据地址 `addr` |
| MSHC ADMA2 / ADMA2_3 | `adma_des` | 描述符地址 `adma_des.cmd_addr` |
| mobile_storage IDMAC | `idmac_descriptor`，传输上限 8191 字节 | 将 `descriptor_addr` 写入 `DBADDR_R`；描述符中另存 `data_addr` |

mobile_storage 使用 `CTRL_R.USE_INTERNAL_DMAC` 选择 IDMAC，`BMOD_R.SWR` 复位，`BMOD_R.DE` 使能，再向 `PLDMND_R`（偏移 `0x84`）写 `1` 触发。普通 kit CPU 读写默认使用前门。
