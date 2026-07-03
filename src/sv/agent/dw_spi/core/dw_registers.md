# DesignWare SPI Registers

## REG/FIELD 命名

代码访问 regmodel 时使用大写 REG/FIELD 句柄，例如 `regmodel.CTRLR0`、`regmodel.BAUDR`、`CTRLR0.SPI_FRF`。

## CTRLR0

| Field | Value | Effect |
|---|---:|---|
| `SSI_IS_MST` | `1` | 主机模式 |
| `SSI_IS_MST` | `0` | 从机模式 |
| `SPI_FRF` | `0` | 单倍速标准模式 |
| `SPI_FRF` | `1` | 2 倍速 enhanced 模式 |
| `SPI_FRF` | `2` | 4 倍速 enhanced 模式 |
| `SPI_FRF` | `3` | 8 倍速 enhanced 模式 |

## BAUDR

`BAUDR` 只能写 2 的倍数。

`sclk_out = ssi_clk / BAUDR`。

`ssi_clk` 是输入 DesignWare SPI/SSI 控制器的参考时钟。输出到从机的频率最大按 6 MHz 约束，常用配置为 6 MHz。

## DMACR

| Field | Bit | Effect |
|---|---:|---|
| `RDMAE` | `0` | 使能接收 DMA request |
| `TDMAE` | `1` | 使能发送 DMA request |

当 transfer 的 `use_dma` 为 1 时，寄存器配置根据传输方向打开对应 bit：读类传输打开 `RDMAE`，写类传输打开 `TDMAE`。

## SR

| Field | Effect |
|---|---|
| `RFF` | 收 FIFO 满 |
| `RFNE` | 收 FIFO 不为空 |
| `TFE` | 发 FIFO 空 |
| `TFNF` | 发 FIFO 不满 |
| `BUSY` | 总线忙碌 |

## ISR

| Field | Effect |
|---|---|
| `DONES` | SSI 总线传输完毕 |

## DR

写 `DR` 表示写入一个数据，读 `DR` 表示读出一个数据。

`DR` 与 FIFO 交互，寄存器宽度为 32 bit。常见交互粒度为 8 bit；在特定寄存器配置下可按 32 bit 交互。
