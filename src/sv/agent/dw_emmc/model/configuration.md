# Configuration

## boot_configuration

| 字段 | 说明 |
| --- | --- |
| `power_up_time_ns` | 首次上电等待时间，默认 `200000` |
| `relative_addr` | RCA，默认 `1`，禁止为 `0` |
| `voltage` | 工作电压；eMMC 默认 `V1_8`，SD/SDIO 默认 `V3_3` |
| `voltage_switch_time_us` | 电压切换等待时间，默认 `250` |
| `default_data_width` | 默认数据位宽；eMMC 默认 `8`，SD/SDIO 默认 `4` |
| `default_bus_speed_mode` | 默认速度模式；eMMC 默认 `HS400` |
| `sram_size` | SRAM 容量，必须为 512 整数倍 |

## eMMC 频率

| 字段 | 默认 |
| --- | --- |
| `frequence_legacy` | `26000000` |
| `frequence_high_speed_sdr` | `50000000` |
| `frequence_high_speed_ddr` | `50000000` |
| `frequence_hs200` | `200000000` |
| `frequence_hs400` | `200000000` |

## SD/SDIO 能力

| 字段 | 默认 |
| --- | --- |
| `sd_capacity_type` | `SDXC` |
| `auto_card_insert` | `1` |
| `is_support_sdr12` | `1` |
| `is_support_sdr25` | `1` |
| `is_support_sdr50` | `1` |
| `is_support_sdr104` | `1` |
| `is_support_ddr50` | `0` |

## SD/SDIO 频率

| 字段 | 默认 |
| --- | --- |
| `frequence_ds` | `24000000` |
| `frequence_sdr12` | `24000000` |
| `frequence_hs` | `50000000` |
| `frequence_sdr25` | `50000000` |
| `frequence_sdr50` | `100000000` |
| `frequence_ddr50` | `100000000` |
| `frequence_sdr104` | `200000000` |

## check_clock_configuration

| 字段 | 说明 |
| --- | --- |
| `should` | 总开关，默认 `0` |
| `should_<clk>` | 单个非 volatile clock 检查开关 |
| `frequence_<clk>` | 期望频率，单位 Hz |
| `tolerance_<clk>` | 容差，百分比 |

volatile clock 不生成 `should_<clk>`、`frequence_<clk>`、`tolerance_<clk>` 字段。

