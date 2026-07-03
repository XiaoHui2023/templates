# DesignWare SPI Registers

## CTRLR0

| Field | Value | Effect |
|---|---:|---|
| `ssi_is_mst` | `1` | 主机模式 |
| `ssi_is_mst` | `0` | 从机模式 |
| `spi_frf` | `0` | 单倍速标准模式 |
| `spi_frf` | `1` | 2 倍速 enhanced 模式 |
| `spi_frf` | `2` | 4 倍速 enhanced 模式 |
| `spi_frf` | `3` | 8 倍速 enhanced 模式 |

## BAUDR

`BAUDR` 只能写 2 的倍数。

输出频率 = 输入时钟频率 / `BAUDR`。

输出频率最大按 6 MHz 约束，常用配置为 6 MHz。

## SR

| Field | Effect |
|---|---|
| `rff` | 收 FIFO 满 |
| `rfne` | 收 FIFO 不为空 |
| `tfe` | 发 FIFO 空 |
| `tfnf` | 发 FIFO 不满 |
| `busy` | 总线忙碌 |

## ISR

| Field | Effect |
|---|---|
| `dones` | SSI 总线传输完毕 |

## DR

写 `DR` 表示写入一个数据，读 `DR` 表示读出一个数据。

`DR` 与 FIFO 交互，寄存器宽度为 32 bit。常见交互粒度为 8 bit；在特定寄存器配置下可按 32 bit 交互。
