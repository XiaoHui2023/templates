# Command

## command_request

| 字段 | 说明 |
| --- | --- |
| `cmd_index` | CMD 编号 |
| `argument` | 写入 `ARGUMENT_R` 的 32-bit 参数 |
| `resp` | 协议响应类型 |
| `access_request` | 寄存器访问 request |
| `chk_err_request` | 错误检查 request |
| `rst_request` | reset request |

`resp_type_select` 和 `NO_RESP` 属于 `access_request`，访问写法为 `cmd_request.access_request.resp_type_select`、`cmd_request.access_request.NO_RESP`。

## 基础命令

| 命令 | 类 | argument | response | 关键点 |
| --- | --- | --- | --- | --- |
| CMD0 | `go_idle_state_command_request` | `0` | NR | idle |
| CMD1 | `send_op_cond_command_request` | `ocr` | R3 | eMMC OCR |
| CMD2 | `all_send_cid_command_request` | `0` | R2 | CID |
| CMD3 | `set_relative_addr_command_request` | `rca << 16` | R1 | eMMC RCA 默认来自 `boot_cfg.relative_addr` |
| CMD7 | `select_card_command_request` | `rca << 16` | R1/R1b | `busy == 1` 时 R1b |
| CMD8 | `send_ext_csd_command_request` | `0` | R1 | eMMC 读 512B EXT_CSD |
| CMD9 | `send_csd_command_request` | `rca << 16` | R2 | CSD |
| CMD10 | `send_cid_command_request` | `rca << 16` | R2 | CID |
| CMD12 | `stop_transmission_command_request` | `rca/hpi` | R1/R1b | 停止传输 |
| CMD13 | `send_status_command_request` | `rca/sqs/hpi` | R1 | 状态查询 |
| CMD15 | `go_inactive_state_command_request` | `rca << 16` | NR | inactive |
| CMD16 | `set_blocklen_command_request` | `block_length` | R1 | 默认 512 |
| CMD23 | `set_block_count_command_request` | `number_of_blocks` | R1 | 多块读写块数 |

## 读写命令

| 命令 | 类 | argument | 数据方向 | 块选择 |
| --- | --- | --- | --- | --- |
| CMD17 | `read_single_block_command_request` | `data_address` | read | `SINGLE` |
| CMD18 | `read_multiple_block_command_request` | `data_address` | read | `MULTI` |
| CMD24 | `write_block_command_request` | `data_address` | write | `SINGLE` |
| CMD25 | `write_multiple_block_command_request` | `data_address` | write | `MULTI` |

## SD 命令

| 命令 | 类 | 字段 |
| --- | --- | --- |
| CMD5 | `io_send_op_cond_command_request` | `s18r`、`ocr` |
| CMD6 | `switch_func_command_request` | `mode`、`current_limit`、`driver_strength`、`command_system`、`access_mode`、`bus_speed_mode` |
| CMD8 | `send_if_cond_command_request` | `vhs`、`check_pattern` |
| CMD11 | `voltage_switch_command_request` | 固定切换命令 |
| CMD55 | `app_cmd_command_request` | `rca` |

## SDIO CMD53

| 字段 | 说明 |
| --- | --- |
| `rw_flag` | 读写方向 |
| `function_number` | function 编号 |
| `block_mode` | byte / block 模式 |
| `op_code` | 固定地址 / 地址递增 |
| `register_address` | 17-bit 地址 |
| `count` | byte 模式 1-512；block 模式 1-511；0 表示无限 |

`block_mode == BLOCK && count != 1` 时 `multi_blk_sel == MULTI`；其他情况为 `SINGLE`。

## response

| response | `access_request.resp_type_select` | CRC check | index check |
| --- | --- | --- | --- |
| NR | `NO_RESP` | disable | disable |
| R1 | `RESP_LEN_48` | enable | enable |
| R1b | `RESP_LEN_48B` | enable | enable |
| R2 | `RESP_LEN_136` | enable | disable |
| R3 | `RESP_LEN_48` | disable | disable |
| R4 | `RESP_LEN_48` | disable | disable |
| R5/R6/R7 | `RESP_LEN_48` | enable | enable |

