# DesignWare SPI Registers

代码访问 regmodel 时使用大写 REG/FIELD 句柄。大量访问同一 regmodel 时，task 内先用局部句柄 `rm = settings.regmodel`，后续写 `rm.CTRLR0`、`rm.BAUDR`、`rm.CTRLR0.SPI_FRF`。寄存器地址由 regmodel 托管，本模块文档只记录字段语义和配置顺序。

## 配置顺序

1. 写 `SSIENR.SSIC_EN = 0` 关闭控制器。
2. 写 `IMR` 屏蔽或打开需要的中断，写 `ICR` 清中断状态。
3. 写 `SER.SER = 0` 释放片选。
4. 写 `CTRLR0`、`CTRLR1`、`BAUDR`、FIFO threshold、DMA threshold、DMA 地址寄存器、`RX_SAMPLE_DELAY`。
5. 写 `SER.SER` 选择目标片选。
6. 写 `SSIENR.SSIC_EN = 1` 打开控制器。

配置字段时先用 regmodel REG `read()` 刷新镜像，再使用 FIELD `set()`，最后对所属 REG 调 `write()`。`status` 只作为 RAL API 形参保留，不逐次检查 `UVM_IS_OK`。不要使用 `update()`，不要在 core 里拼接完整寄存器值，也不要在 configuration 里保存寄存器地址。

## CTRLR0

| Field | Value | Effect |
| --- | ---: | --- |
| `SSI_IS_MST` | `1` | 主机模式 |
| `SSI_IS_MST` | `0` | 从机模式 |
| `SPI_FRF` | `0` | 单倍速标准模式 |
| `SPI_FRF` | `1` | 2 倍速 enhanced 模式 |
| `SPI_FRF` | `2` | 4 倍速 enhanced 模式 |
| `SCPH` | `spi_mode[0]` | SPI phase |
| `SCPOL` | `spi_mode[1]` | SPI polarity |
| `TMOD` | `0` | TX and RX |
| `TMOD` | `1` | TX only |
| `TMOD` | `2` | RX only |
| `TMOD` | `3` | EEPROM read |
| `DFS` | `data_frame_bits - 1` | 数据帧位宽 |

PSSI/HSSI 的 bit layout 可能不同，代码必须通过 FIELD 名访问，不依赖固定 bit slice。

## CTRLR1

| Field | Effect |
| --- | --- |
| `NDF` | receive-only 或 EEPROM-read 类传输的数据帧数量配置 |

`NDF` 来自单次 register `configuration`，由 sequence 层根据 transfer req 推导。`NDF` 以 DFS frame 为单位，不以 byte 为单位；当 `CTRLR0.DFS` 大于 8 时，必须先把 payload byte length 转成 bit length，再按 `data_frame_bits` 向上取整得到 frame 数。

```text
payload_bits = payload_bytes * 8
frames = ceil(payload_bits / data_frame_bits)
NDF = max(frames, 1) - 1
```

例如读取 4 byte 数据时，`data_frame_bits == 8` 得到 4 frame，`NDF == 3`；`data_frame_bits == 32` 得到 1 frame，`NDF == 0`。

## SPI_CTRLR0

`SPI_CTRLR0` 用于 DWC_ssi enhanced SPI、XIP、DDR、HyperBus 等扩展传输控制。当前 flash enhanced flow 配置 `WAIT_CYCLES`、`INST_L`、`ADDR_L` 和 `TRANS_TYPE`；XIP、DDR、HyperBus、mode bits 和 data mask 字段只记录语义，等具体 flow 消费时再加入代码。

| Field | Effect |
| --- | --- |
| `CLK_STRETCH_EN` | 使能 SPI transfer 的 clock stretching 能力 |
| `XIP_PREFETCH_EN` | 使能 DWC_ssi 的 XIP pre-fetch 功能 |
| `SPI_RXDS_SIG_EN` | HyperBus transfer 的 address 和 command phase 使能 RXDS signaling |
| `SPI_DM_EN` | SPI data mask enable |
| `XIP_INST_EN` | XIP instruction enable |
| `XIP_DFS_HC` | 固定 XIP transfer 的 DFS |
| `SPI_RXDS_EN` | Read data strobe enable |
| `INST_DDR_EN` | Instruction DDR enable |
| `SPI_DDR_EN` | SPI DDR enable |
| `WAIT_CYCLES` | Dual/quad mode 下 control frames 发送和 data reception 之间的 wait cycles；当前增强读常用 8 拍 |
| `XIP_MD_BIT_EN` | XIP mode 下使能 mode bits |

### `XIP_MBL`

| Value | Mode bits length |
| ---: | --- |
| `0` | 2 bit |
| `1` | 4 bit |
| `2` | 8 bit |
| `3` | 16 bit |

### `INST_L`

Dual/quad mode 下 instruction length。

| Value | Instruction length |
| ---: | --- |
| `0` | no instruction |
| `1` | 4 bit |
| `2` | 8 bit |
| `3` | 16 bit |

### `ADDR_L`

`ADDR_L` 定义要发送的 address length。

| Value | Address length |
| ---: | --- |
| `0` | no address |
| `1` | 4 bit |
| `2` | 8 bit |
| `...` | 每递增 1 增加 4 bit |
| `f` | 60 bit |

当前 flash flow 使用 32 bit flash/model 地址；`ADDR_L` 是控制器线上 address phase 长度字段，不等同于 scoreboard 地址宽度。

### `TRANS_TYPE`

`TRANS_TYPE` 定义 instruction 和 address 的传输格式。

| Value | Transfer format |
| ---: | --- |
| `0` | instruction 和 address 都以 standard SPI mode 发送 |
| `1` | instruction 以 standard SPI mode 发送，address 以 `CTRLR0.SPI_FRF` 指定格式发送 |
| `2` | instruction 和 address 都以 `CTRLR0.SPI_FRF` 指定格式发送 |

## SSIENR

| Field | Value | Effect |
| --- | ---: | --- |
| `SSIC_EN` | `1` | 使能 SSI 控制器 |
| `SSIC_EN` | `0` | 关闭 SSI 控制器 |

配置 `CTRLR0`、`CTRLR1`、`BAUDR`、FIFO、DMA、sample delay 前先关闭控制器，配置稳定后再打开。

## SER

| Field | Effect |
| --- | --- |
| `SER` | 片选 mask。配置阶段先写 `0`，最后写入本次传输的 `cs_id` 对应 mask |

平台级 CS 行为可由 callback 注入。寄存器 `SER` 和 callback 的片选动作都围绕 primitive transfer 边界执行。

## BAUDR

| Field | Effect |
| --- | --- |
| `SCKDV` | 偶数分频值 |

`sclk_out = ssi_clk / BAUDR`。`ssi_clk` 是输入 DesignWare SPI/SSI 控制器的参考时钟。`BAUDR` 由测量到的 `ssi_clk` 和目标串行输出频率推导，不是固定默认值。公式见 `core/formulas.md`。

## TXFTLR / RXFTLR

| Register | Field | Effect |
| --- | --- | --- |
| `TXFTLR` | `TFT` | TX FIFO threshold |
| `RXFTLR` | `RFT` | RX FIFO threshold |

threshold 必须小于 Python settings 配置的 FIFO 深度，默认 FIFO 深度为 32 字节。

## IMR / ICR / ISR

| Register | Field | Effect |
| --- | --- | --- |
| `IMR` | `TXEIM` | TX empty interrupt mask |
| `IMR` | `TXOIM` | TX overflow interrupt mask |
| `IMR` | `RXUIM` | RX underflow interrupt mask |
| `IMR` | `RXOIM` | RX overflow interrupt mask |
| `IMR` | `RXFIM` | RX full interrupt mask |
| `IMR` | `MSTIM` | Multi-master contention interrupt mask |
| `ICR` | full register write | 清中断状态 |
| `ISR` | `DONES` | SSI 总线传输完毕 |

本模板的 transfer operation 通过 top interface 等待 `intr`，寄存器配置仍保留 `IMR/ICR` 的初始化入口。

## SR

| Field | Effect |
| --- | --- |
| `RFF` | RX FIFO 满 |
| `RFNE` | RX FIFO 不为空 |
| `TFE` | TX FIFO 空 |
| `TFNF` | TX FIFO 不满 |
| `BUSY` | 总线忙碌 |

PIO 真实搬运使用 `TFNF/RFNE` 驱动：写传输等待 `TFNF` 后写 `DR`，读传输等待 `RFNE` 后读 `DR`。scoreboard 只接收最终写入的 expected data 或读回的 actual data，不替代 DUT 读路径。

## DMACR / DMATDLR / DMARDLR

| Register | Field | Effect |
| --- | --- | --- |
| `DMACR` | `RDMAE` | 使能外部 RX DMA request |
| `DMACR` | `TDMAE` | 使能外部 TX DMA request |
| `DMACR` | `IDMAE` | 使能内部 DMA |
| `DMACR` | `AINC` | 使能 AXI 地址自增 |
| `DMATDLR` | `DMATDL` | TX DMA threshold |
| `DMARDLR` | `DMARDL` | RX DMA threshold |

Python `internal_dma` 和 `external_dma` 互斥。两者都关闭时不生成 DMA 配置代码。

内部 DMA 模式下，transfer 的 `use_dma` 为 `1` 时按方向设置 `RDMAE/TDMAE`，同时设置 `IDMAE = 1` 和 `AINC = 1`。数据搬运通过 callback 注入的 CPU 32-bit 读写访问 `axi_addr` buffer；寄存器配置不放在 callback 内。

外部 DMA 模式下，transfer 的 `use_dma` 为 `1` 时根据传输方向设置 `RDMAE/TDMAE`。外部 DMA 不使用内部 CPU buffer mover。

## AXIAWLEN / AXIARLEN / SPIDR / SPIAR / AXIAR0

内部 DMA 模式还需要配置 SPI instruction、SPI device address 和 AXI buffer address。仅在 `internal_dma: true` 且 `use_dma == 1` 时写这些寄存器；外部 DMA 和无 DMA 模式不写。

| Register | Field | Source |
| --- | --- | --- |
| `AXIAWLEN` | `AWLEN` | per-transfer `awlen << 8` |
| `AXIARLEN` | `ARLEN` | per-transfer `arlen << 8` |
| `SPIDR` | `SPI_INST` | 当前 transfer opcode，例如 flash read/page program opcode |
| `SPIAR` | `SDAR` | 当前 payload address 的低 32 bit，表示 SPI device/flash address |
| `AXIAR0` | `AXIAR0` | per-transfer `axi_addr` |

`SPIAR.SDAR` 是外设侧地址，当前 flash flow 使用 32 bit flash/model 地址。`AXIAR0.AXIAR0` 是 DMA 访问系统内存的 AXI 地址，不等同于 flash 地址；kit 和 per-transfer configuration 提供 `axi_addr`，默认值为 0。

## DR

写 `DR` 表示写入一个数据项，读 `DR` 表示读出一个数据项。`DR` 与 FIFO 交互，寄存器宽度为 32 bit。常见交互粒度为 8 bit；如果数据帧配置选择更宽位宽，单次交互粒度随配置变化。

## RX_SAMPLE_DELAY

| Field | Effect |
| --- | --- |
| `RSD` | RX sample delay 配置 |

只有 `configuration.write_rx_sample_delay` 为 `1` 时才写 `RX_SAMPLE_DELAY.RSD`。寄存器名使用 `RX_SAMPLE_DELAY`，不要写成 `RX_SAMPLE_DLY`。
