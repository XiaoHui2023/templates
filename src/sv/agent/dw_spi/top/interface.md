# interface

## `dw_spi_interface`

入口 interface 类型名使用 `interface` 后缀，例如 `dw_spi_interface`。

| 项 | 值 |
| --- | --- |
| `timeunit` | `1ns` |
| `timeprecision` | `1fs` |

### 端口

信号从端口输入。未接的可选信号用 X/Z 表示，检查 sequence 会按未连接处理。

| 端口 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| `hclk` | input | `logic` | AHB/APB 总线与寄存器模块参考时钟 |
| `ssi_clk` | input | `logic` | 输入 DesignWare SPI/SSI 控制器的参考时钟 |
| `intr` | input | `logic` | 中断信号 |

### 子 interface

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| `hclk_if` | `dw_spi_clock_if` | `hclk` 连接状态与频率测量 |
| `ssi_clk_if` | `dw_spi_clock_if` | `ssi_clk` 连接状态与频率测量 |
| `interrupt_if` | `dw_spi_interrupt_if` | `intr` 连接状态与断言检查 |

### 查询函数

| 函数 | 返回 | 说明 |
| --- | --- | --- |
| `has_hclk()` | `bit` | `hclk` 不是 X/Z |
| `has_ssi_clk()` | `bit` | `ssi_clk` 不是 X/Z |
| `has_irq()` | `bit` | `intr` 不是 X/Z |

### 频率函数

| 函数/task | 说明 |
| --- | --- |
| `baudr_for_target(ssi_clk_hz, target_hz)` | 使用整数 Hz 计算不小于 2 的偶数 BAUDR，满足 `ssi_clk_hz / BAUDR` 不超过目标频率 |
| `measure_hclk_frequency_hz(frequency_hz, min_frequency_hz)` | 调用 `hclk_if` 测量 `hclk` 频率，返回整数 Hz |
| `measure_ssi_clk_frequency_hz(frequency_hz, min_frequency_hz)` | 调用 `ssi_clk_if` 测量 `ssi_clk` 频率，返回整数 Hz |
| `wait_interrupt_asserted(timeout_ssi_clk_cycles, timed_out, missing_signal)` | 等待 `intr` 拉高；用 `ssi_clk` 计数超时，缺少 `intr` 或 `ssi_clk` 时置 `missing_signal` |

## `dw_spi_clock_if`

`clock_if` 接收一个时钟端口 `clk`。

| 函数/task | 说明 |
| --- | --- |
| `is_connected()` | `clk` 不是 X/Z |
| `measure_frequency_hz(frequency_hz, min_frequency_hz, tolerance_ppm)` | 采样一个周期并计算整数 Hz；超时由最低频率和容差计算；未连接或超时返回 `0` |

## `dw_spi_interrupt_if`

`interrupt_if` 接收中断端口 `intr`。

| 函数 | 返回 | 说明 |
| --- | --- | --- |
| `is_connected()` | `bit` | `intr` 不是 X/Z |
| `is_asserted()` | `bit` | `intr` 已连接且为 1 |

## sequence 使用

`sequence/operation/check_clock` 通过 `p_sequencer.settings.vif` 访问 `dw_spi_interface`。

`sequence/operation/transfer` 发起传输后通过 `wait_interrupt_asserted()` 等待 `intr`。超过 `settings.interrupt_timeout_ssi_clk_cycles` 个 `ssi_clk` 周期时 fatal，防止仿真卡死。

当 `hclk` 或 `ssi_clk` 未连接时，检查会跳过对应时钟。

`hclk` 和 `ssi_clk` 之间没有频率关系检查。默认只检查两者各自高于最低频率 24MHz，容差 1%。

`ssi_clk` 是控制器输入时钟。输出到从机的串行时钟按 `sclk_out = ssi_clk / BAUDR` 计算，check_clock 会用这个公式检查 `sclk_out` 是否超过 `max_output_hz`，并给出推荐 BAUDR。
