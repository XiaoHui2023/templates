# DesignWare SPI Registers

代码访问 regmodel 时使用大写 REG/FIELD 句柄。大量访问同一个 regmodel 时，task 内先保存 `rm = settings.regmodel`，后续写 `rm.CTRLR0`、`rm.BAUDR`、`rm.CTRLR0.SPI_FRF`。寄存器地址由 regmodel 托管，本文件只记录字段语义和配置顺序。

## 配置顺序

1. 写 `SSIENR.SSIC_EN = 0` 关闭控制器。
2. 写 `IMR` 配置 FIFO/error mask，写 `ICR` 清旧中断状态。
3. 写 `SER.SER = 0` 释放片选。
4. 写 `CTRLR0`、`SPI_CTRLR0`、`CTRLR1`、`BAUDR`、FIFO threshold、DMA threshold、DMA 地址寄存器、`RX_SAMPLE_DELAY`。
5. 写 `SSIENR.SSIC_EN = 1` 打开控制器。
6. 保持 `SER.SER = 0` 返回。`SER.SER = cfg.ser` 由 transfer sequence 在 PIO FIFO 预填或 DMA 启动边界执行；completion 后必须写回 0。

字段配置时先用 REG `read()` 刷新镜像，再用 FIELD `set()`，最后对所属 REG 调 `write()`。`status` 只作为 RAL API 形参保留，不逐次检查 `UVM_IS_OK`。不要使用 `update()`，不要在 core 里拼接完整寄存器值，也不要在 `configuration` 里保存寄存器地址。

## CTRLR0

| Field | Value | Effect |
| --- | ---: | --- |
| `SSI_IS_MST` | `1` | 主机模式 |
| `SSI_IS_MST` | `0` | 从机模式 |
| `SPI_FRF` | `0` | 1 倍速标准模式 |
| `SPI_FRF` | `1` | 2 倍速 enhanced 模式 |
| `SPI_FRF` | `2` | 4 倍速 enhanced 模式 |
| `SCPH` | `spi_mode[0]` | SPI phase |
| `SCPOL` | `spi_mode[1]` | SPI polarity |
| `SSTE` | bit `[14]` | 标准 SPI 帧间片选 toggle enable |
| `TMOD` | `0` | TX and RX |
| `TMOD` | `1` | TX only |
| `TMOD` | `2` | RX only |
| `TMOD` | `3` | EEPROM read |
| `DFS` | `data_frame_bits - 1` | 数据帧位宽 |

Flash page-program 使用 `TMOD=1 / TX_ONLY`，因为 opcode/address/payload 都是 master 向 flash 发送，且写流程不使用 dummy clock。Enhanced read 使用 `TMOD=2 / RX_ONLY`，由 `SPI_CTRLR0` 的 instruction/address/dummy 字段描述接收前的发送阶段；不要把 page-program 配成 `TX_AND_RX`。

`SSTE` 只描述标准 SPI 帧间分割行为。`SCPH=0` 且 `SSTE=1` 时，每帧数据之间 `ss_*_n` 会拉高再拉低，`SCLK` 停在默认电平；`SSTE=0` 时 `ss_n` 全程保持有效，`SCLK` 连续运行。该行为本质上是 frame 间分割，不等同于完整 SPI memory operation 的 CS window。当前模板每次 transfer 显式写 `CTRLR0.SSTE = 0`，避免收发数据时帧间片选 toggle 破坏连续性。

PSSI/HSSI 的 bit layout 可能不同，代码必须通过 FIELD 名访问，不依赖固定 bit slice。本模板 regmodel 只有 `DFS`，没有 `DFS_32`。

## CTRLR1

`CTRLR1.NDF` 表示 data phase 的 frame 数，不包含 instruction、address 或 dummy/wait phase。Enhanced TX-only 使用它限制要发送的 payload data frames，并在 FIFO 暂时耗尽时配合 clock stretching 保持本次传输；enhanced read / receive-only 使用它指定要接收的 data frames。寄存器字段存放 `actual_data_frames - 1`。

当前 byte payload API 按 `data_frame_bits` 把 payload byte 数换算为 data frame 数。8 bit DFS 时，data frame 数等于 payload byte 数；DFS 大于 8 时按 DFS 分组。Instruction/address 仍属于同一个 CS window，但由 `SPI_CTRLR0.INST_L/ADDR_L` 描述，不计入 NDF。

```text
actual_data_frames = ceil(payload_bytes * 8 / data_frame_bits)
CTRLR1.NDF = actual_data_frames == 0 ? 0 : actual_data_frames - 1
```

模板通过 `settings.ctrlr1_ndf_max` 记录本 IP 变体允许写入的最大 NDF 编码值，默认 `65535`。如果 payload data frames 推导出的 `CTRLR1.NDF` 超过该上限，`register_config_builder` 必须直接 fatal。FIFO refill 只解决 CPU 如何持续喂 `DR`，不能突破一次 SPI transaction 的 NDF 寄存器上限。

## SPI_CTRLR0

`SPI_CTRLR0` 用于 DWC_ssi enhanced SPI、XIP、DDR、HyperBus 等扩展传输控制。当前 flash enhanced flow 配置 `INST_L`、`ADDR_L` 和 `TRANS_TYPE`；接收类 transfer 还配置 `WAIT_CYCLES`。XIP、DDR、HyperBus、mode bits 和 data mask 字段只记录语义，等具体 flow 消费时再加入代码。

| Field | Effect |
| --- | --- |
| `CLK_STRETCH_EN` | enhanced transfer 的 SCLK stall 能力。尤其在 `RX_ONLY` / DMA 传输中，当 RX FIFO 将满或数据未就绪时，master 可主动 stall SCLK，避免 FIFO 溢出或数据 underrun。当前模板在 enhanced transfer 中写 1。 |
| `XIP_PREFETCH_EN` | 使能 DWC_ssi XIP pre-fetch |
| `XIP_MBL` | XIP mode bits length：0=2 bit，1=4 bit，2=8 bit，3=16 bit |
| `SPI_RXDS_SIG_EN` | HyperBus address/command phase 使能 RXDS signaling |
| `SPI_DM_EN` | SPI data mask enable |
| `XIP_INST_EN` | XIP instruction enable |
| `XIP_DFS_HC` | 固定 XIP transfer 的 DFS |
| `SPI_RXDS_EN` | Read data strobe enable |
| `INST_DDR_EN` | Instruction DDR enable |
| `SPI_DDR_EN` | SPI DDR enable |
| `WAIT_CYCLES` | dual/quad mode control frames 与 data reception 之间的 wait cycles |
| `INST_L` | instruction length：0=no instruction，1=4 bit，2=8 bit，3=16 bit |
| `XIP_MD_BIT_EN` | XIP mode bits enable |
| `ADDR_L` | address length：0=no address，1=4 bit，2=8 bit，递增到 f=60 bit |
| `TRANS_TYPE` | 0=instruction/address 都 standard，1=instruction standard/address 按 `SPI_FRF`，2=都按 `SPI_FRF` |

当前 flash flow 的 `TRANS_TYPE` 由 `transfer_req.instruction_lanes` 和 `address_lanes` 共同推导，不直接等于 enhanced。`TRANS_TYPE=0` 表示 instruction/address 都走标准单线，用于 PP、DPP、QPP 和 output-read；`TRANS_TYPE=1` 表示 instruction 单线、address 按 `SPI_FRF`，用于 `READ2X 0xBB` 和 `READ4X 0xEB`；`TRANS_TYPE=2` 表示 instruction/address 都按 `SPI_FRF`，保留给显式声明多线 instruction/address 的扩展指令包。

`WAIT_CYCLES` 只用于 enhanced 接收类 transfer，例如 `RX_ONLY` / `EEPROM_READ` / `TX_AND_RX` 读路径中控制帧到数据接收之间的等待。Flash write/program 不使用 dummy clock，也不把 dummy 写成 `DR` byte stream。

当前内置 read opcode 的 wait/dummy SCLK 数为：`READ1X 03h=8`、`FASTREAD1X 0Bh=16`、`READ2X BBh=12`、`READ4X EBh=10`。后三者在 enhanced `RX_ONLY` 路径写入 `WAIT_CYCLES`。

## SSIENR / SER / BAUDR

| Register | Field | Effect |
| --- | --- | --- |
| `SSIENR` | `SSIC_EN` | `1` 使能 SSI 控制器，`0` 关闭 |
| `SER` | `SER` | 片选 mask |
| `BAUDR` | `SCKDV` | 偶数分频值 |

`sclk_out = ssi_clk / BAUDR`。`ssi_clk` 是输入 DesignWare SPI/SSI 控制器的参考时钟。`BAUDR` 由测量到的 `ssi_clk` 和目标串行输出频率推导，不是固定默认值。公式见 [formulas.md](formulas.md)。

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
| `ISR` | `DONES` | 本地 DWC SSI/内置 DMA 扩展完成位 |

公共 Linux `spi-dw` ISR 只暴露 FIFO/error 类中断位，没有通用 `DONES`。本模板只在内置 DMA transfer 中使用 `ISR.DONES` 确认完成；非 DMA PIO 不使用它，默认轮询 `SR.TFE && !SR.BUSY`。`TXEIM/RXFIM` 等 FIFO 中断不能当作 transfer done 使用；详细边界见 [interrupts.md](../interrupts.md)。

## SR

| Field | Effect |
| --- | --- |
| `RFF` | RX FIFO 满 |
| `RFNE` | RX FIFO 不为空 |
| `TFE` | TX FIFO 空 |
| `TFNF` | TX FIFO 不满 |
| `BUSY` | 总线忙碌 |

PIO 搬运使用 `TFNF/RFNE` 驱动：写传输等待 `TFNF` 后写 `DR`，读传输等待 `RFNE` 后读 `DR`。非 DMA PIO 的最终完成由 `SR.TFE && !SR.BUSY` 判断。`SR.TFNF` 只表示 TX FIFO 不满，不能代表 transmit complete。

## DMA Registers

| Register | Field | Effect |
| --- | --- | --- |
| `DMACR` | `RDMAE` | 使能 RX DMA request |
| `DMACR` | `TDMAE` | 使能 TX DMA request |
| `DMACR` | `IDMAE` | 使能内置 DMA |
| `DMACR` | `AINC` | 使能 AXI 地址自增 |
| `DMATDLR` | `DMATDL` | TX DMA threshold |
| `DMARDLR` | `DMARDL` | RX DMA threshold |
| `AXIAWLEN` | `AWLEN` | per-transfer `awlen << 8` |
| `AXIARLEN` | `ARLEN` | per-transfer `arlen << 8` |
| `SPIDR` | `SPI_INST` | 当前 transfer opcode |
| `SPIAR` | `SDAR` | 当前 SPI device/flash address，32 bit |
| `AXIAR0` | `AXIAR0` | per-transfer `axi_addr` |

Python `internal_dma` 和 `external_dma` 互斥。两者都关闭时不生成 DMA 配置代码。内置 DMA 使用 CPU callback 准备或读回 AXI buffer；外部 DMA 不使用内置 CPU buffer mover。

## DR / RX_SAMPLE_DELAY

写 `DR` 表示写入一个数据项，读 `DR` 表示读出一个数据项。`DR` 与 FIFO 交互，寄存器宽度为 32 bit；常见交互粒度为 8 bit，具体粒度随数据帧配置变化。

Enhanced PIO flash transfer 的 control phase 使用专用 FIFO entry 形状：instruction 低位对齐写一个 32-bit DR item，完整 address 低位对齐再写一个 32-bit DR item，payload 随后按 data frame 写入。因此 3-byte address 不是三个 FIFO entries；QPP 的 instruction + address 总共占两个 control entries，但两者都不计入 NDF。Standard SPI 不使用该 packing，仍逐 byte 写 instruction/address。

`RX_SAMPLE_DELAY.RSD` 只在 `configuration.write_rx_sample_delay == 1` 时写入。寄存器名使用 `RX_SAMPLE_DELAY`，不要写成 `RX_SAMPLE_DLY`。

## SPIDR.SPI_INST Packing

`SPIDR.SPI_INST` is a 16-bit internal-DMA instruction container, not the instruction length. The actual instruction length is configured by `SPI_CTRLR0.INST_L`, derived from `inst_bytes`.

The current SPI flash opcode model carries one opcode byte. For internal DMA, pack it as:

```text
SPI_INST = {opcode, 8'h00}
```

Do not write a 1-byte opcode as low-aligned `16'h00xx` or as 32-bit `{24'h0, opcode}`. With `INST_L=2`, the hardware should consume an 8-bit instruction from the high byte of the 16-bit instruction container.
