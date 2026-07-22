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
| `min_frequence_<clk>` | `presence` / `relation` 检查使用的最小频率，单位 Hz |
| `frequence_<clk>` | `frequency` 检查使用的期望频率，单位 Hz |
| `tolerance_<clk>` | `frequency` 检查使用的容差，百分比 |
| `relation_tolerance_<clk>` | `relation` 中 `==` 比较使用的容差，百分比 |

字段只对 `models.py` 中 `monitored_clocks[].enable == true` 的 clock 生成。

默认只生成 `hclk`，并按 `presence` 检查。SV 里没有 clock 检查开关；clock 端口未连接或为 X/Z 时跳过，已连接时按该 clock 的类型检查。

## clock_defaults

| 字段 | 默认值 |
| --- | --- |
| `crystal_frequence` | `24000000` |
| `tmclk_frequence` | `1000000` |
| `cqetmclk_frequence` | `1000000` |
| `tolerance` | `5` |
| `cclk_rx_relation_operator` | `==` |

生成时先创建内置 clock 默认表，再用 `monitored_clocks` 中的同名字段覆盖。单个 clock 的 `enable`、`min_frequence`、`frequence`、`tolerance`、`relation_operator` 可在 `monitored_clocks` 中覆盖。
