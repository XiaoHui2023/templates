# Interface

## `dw_spi_interface`

入口 interface 类型名使用 `interface` 后缀，例如 `dw_spi_interface`。信号从端口输入；未接的可选信号可用 X/Z 表示。

| 端口 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| `hclk` | input | `logic` | AHB/APB 总线与寄存器模块参考时钟 |
| `ssi_clk` | input | `logic` | 输入 DesignWare SPI/SSI 控制器的参考时钟 |
| `intr` | input | `logic` | 顶层中断信号 |

## 子 interface

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| `hclk_if` | `dw_spi_clock_if` | `hclk` 连接状态与频率测量 |
| `ssi_clk_if` | `dw_spi_clock_if` | `ssi_clk` 连接状态与频率测量 |
| `interrupt_if` | `dw_spi_interrupt_if` | `intr` 连接状态与断言检查 |

## 查询和测量

| 函数/task | 说明 |
| --- | --- |
| `has_hclk()` | `hclk` 不是 X/Z |
| `has_ssi_clk()` | `ssi_clk` 不是 X/Z |
| `has_irq()` | `intr` 不是 X/Z |
| `measure_hclk_frequency_hz(frequency_hz, min_frequency_hz)` | 测量一个完整 `hclk` 周期并返回整数 Hz |
| `measure_ssi_clk_frequency_hz(frequency_hz, min_frequency_hz)` | 测量一个完整 `ssi_clk` 周期并返回整数 Hz |
| `wait_interrupt_asserted(timeout_ssi_clk_cycles, min_ssi_clk_hz, tolerance_ppm, timed_out, missing_signal)` | 等待 `intr` 拉高；用 `ssi_clk` 计数超时，并用最低频率推导仿真时间兜底超时 |

## sequence 使用

`sequence/operation/check_clock` 通过 `p_sequencer.settings.vif` 访问 `dw_spi_interface`。`hclk` 和 `ssi_clk` 互相没有频率关系检查，默认只检查各自高于最低频率 24 MHz，容差 1%。`check_clock` 不检查 `sclk_out`；输出频率由寄存器配置阶段选择 `BAUDR` 控制。

`sequence/operation/transfer` 只有在内置 DMA transfer、`completion_mode` 允许中断、且 `intr` 已连接时，才通过 `wait_interrupt_asserted()` 等待 top `intr`，随后读取 `ISR.DONES`。非 DMA PIO 不通过 top `intr` 判定完成，而是通过 regmodel 轮询 `SR.TFE && !SR.BUSY`。

缺少 `intr`、缺少 `ssi_clk` 或 `min_ssi_clk_hz == 0` 时，`wait_interrupt_asserted()` 置 `missing_signal`。如果 `ssi_clk` 停住，仿真时间兜底超时会避免等待中断时卡死。
