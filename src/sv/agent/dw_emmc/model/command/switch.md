# eMMC CMD6 Switch

## switch_command_request

| 字段 | 说明 |
| --- | --- |
| `access` | EXT_CSD access 类型，进入 `argument[25:24]` |
| `index` | EXT_CSD index，进入 `argument[23:16]` |
| `offset` | EXT_CSD byte offset |
| `value` | 写入值，进入 `argument[15:8]` |
| `cmd_set` | `argument[2:0]` |

`resp == R1b`。

## switch_bus_width_command_request

| 字段 | 说明 |
| --- | --- |
| `enhanced_strobe` | HS400 enhanced strobe |
| `bus_mode_selection` | EXT_CSD `BUS_WIDTH` 写入值 |
| `data_width` | 目标数据位宽 |
| `bus_speed_mode` | 目标速度模式 |

EXT_CSD index: `183` (`0xb7`)。

## switch_hs_timing_command_request

| 字段 | 说明 |
| --- | --- |
| `drive_strength` | 驱动强度 |
| `timing_interface` | EXT_CSD `HS_TIMING` 写入值 |
| `bus_speed_mode` | 目标速度模式 |

EXT_CSD index: `185` (`0xb9`)。

## switch_partition_config_command_request

| 字段 | 说明 |
| --- | --- |
| `boot_ack` | boot ack |
| `boot_partition_enable` | boot 数据源 |
| `boot_partition_access` | 当前访问分区 |

EXT_CSD index: `179` (`0xb3`)。

默认 `boot_partition_enable == BOOT_PARTITION_ENABLE_NO` 且 `boot_partition_access == BOOT_PARTITION_ACCESS_NO` 时不能发送该命令；否则会出现无效 CMD6 `03b30000`。

## HS400 8-bit

| 次序 | argument | 作用 |
| --- | --- | --- |
| 1 | `03b90100` | HS_TIMING -> HIGH_SPEED_SDR |
| 2 | `03b70600` | BUS_WIDTH -> 8bit DDR |
| 3 | `03b90300` | HS_TIMING -> HS400 |

