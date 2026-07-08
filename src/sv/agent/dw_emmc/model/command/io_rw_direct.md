# SDIO CMD52

## io_rw_direct_command_request

| 字段 | 说明 |
| --- | --- |
| `rw_flag` | `0` 读，`1` 写 |
| `function_number` | `0` 为 CCCR，`1-7` 为 FBR |
| `raw_flag` | 写后读回 |
| `register_address` | 17-bit 地址 |
| `write_data` | 8-bit 写数据 |

## bus_interface_control

| 字段 | 说明 |
| --- | --- |
| `bus_width` | CCCR Bus Interface Control 位宽字段 |
| `cd_disable` | card detect disable |
| `data_width` | 目标数据位宽 |

## bus_speed_select

| 字段 | 说明 |
| --- | --- |
| `bss` | bus speed select |
| `shs` | support high speed |
| `bus_speed_mode` | 目标速度模式 |

## fn0_block_size

| 字段 | 说明 |
| --- | --- |
| `lo_hi` | `0` 写低 8 位，`1` 写高 8 位 |
| `local_function_number` | function 编号 |
| `block_length` | function block size |

## io_abort

| 字段 | 说明 |
| --- | --- |
| `as` | Abort Select，选择要 abort 的 function |

## io_enable

| 字段 | 说明 |
| --- | --- |
| `enable` | function enable bitmask |

