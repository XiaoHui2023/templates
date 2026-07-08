# ACMD

## base_acmd_request

| 字段 | 说明 |
| --- | --- |
| `app_cmd_request` | 前置 CMD55 request |

ACMD 由 CMD55 + 目标 ACMD 两步组成。

## ACMD41 sd_send_op_cond_acmd_request

| 字段 | 说明 |
| --- | --- |
| `hcs` | host capacity support |
| `xpc` | SDXC maximum current control |
| `s18a` | 1.8V switching accepted |
| `vdd` | OCR `[23:0]` |

`vdd == 0` 表示查询；此时其他初始化参数也为 0。

## ACMD51 send_scr_acmd_request

| 字段 | 说明 |
| --- | --- |
| `block_count` | 固定 1 |
| `block_size` | 固定 8 |
| `data_present_sel` | 固定 1 |

## ACMD6 set_bus_width_acmd_request

| 字段 | 说明 |
| --- | --- |
| `bus_width` | SD bus width，常用 1 或 4 |

