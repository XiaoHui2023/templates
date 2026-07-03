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
| `ssi_clk` | input | `logic` | SPI/SSI 输出时钟 |
| `intr` | input | `logic` | 中断信号 |

### 子 interface

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| `hclk_if` | `dw_spi_clock_if` | `hclk` 连接状态与频率测量 |
| `ssi_clk_if` | `dw_spi_clock_if` | `ssi_clk` 连接状态与频率测量 |
| `irq_if` | `dw_spi_irq_if` | `intr` 连接状态与断言检查 |

### 查询函数

| 函数 | 返回 | 说明 |
| --- | --- | --- |
| `has_hclk()` | `bit` | `hclk` 不是 X/Z |
| `has_ssi_clk()` | `bit` | `ssi_clk` 不是 X/Z |
| `has_irq()` | `bit` | `intr` 不是 X/Z |

### 频率函数

| 函数/task | 说明 |
| --- | --- |
| `baudr_for_target(input_hz, target_hz)` | 计算不小于 2 的偶数 BAUDR，满足输出频率不超过目标频率 |
| `measure_hclk_frequency_hz(frequency_hz)` | 调用 `hclk_if` 测量 `hclk` 频率 |
| `measure_ssi_clk_frequency_hz(frequency_hz)` | 调用 `ssi_clk_if` 测量 `ssi_clk` 频率 |

## `dw_spi_clock_if`

`clock_if` 接收一个时钟端口 `clk`。

| 函数/task | 说明 |
| --- | --- |
| `is_connected()` | `clk` 不是 X/Z |
| `measure_frequency_hz(frequency_hz, sample_edges, timeout_ns)` | 采样多个上升沿并计算频率；未连接或超时返回 `0.0` |

## `dw_spi_irq_if`

`irq_if` 接收中断端口 `intr`。

| 函数 | 返回 | 说明 |
| --- | --- | --- |
| `is_connected()` | `bit` | `intr` 不是 X/Z |
| `is_asserted()` | `bit` | `intr` 已连接且为 1 |

## sequence 使用

`sequence/operation/check_clock` 通过 `p_sequencer.settings.vif` 访问 `dw_spi_interface`。

当 `hclk` 或 `ssi_clk` 未连接时，检查会跳过对应时钟；当两个时钟都连接时，会检查 `ssi_clk <= hclk / BAUDR` 的关系。
