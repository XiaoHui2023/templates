# DW eMMC 命令

## 通用映射

`command_request` 持有协议字段，`access_request` 持有写寄存器字段。`command_request` 约束把字段同步到 `access_req`：

- `access_req.cmd_index == cmd_index`
- `access_req.argument == argument`
- `access_req.multi_blk_sel == multi_blk_sel`
- `access_req.resp_type_select` 由 `resp` 推导

读取 `resp_type_select` 和 `NO_RESP` 应走 `cmd_req.access_req`。它们不是 `command_request` 成员。

## 基础命令

| 命令 | 模板 | argument | response | 关键点 |
| --- | --- | --- | --- | --- |
| CMD0 | `go_idle_state` | 默认 0 | NR | 复位到 idle |
| CMD1 | `send_op_cond` | `ocr` | R3 | eMMC 查询 OCR |
| CMD2 | `all_send_cid` | 默认 0 | R2 | 读取 CID |
| CMD3 | `set_relative_addr` | `rca << 16` | R1 | eMMC `rca != 0`，默认来自 `boot_cfg.relative_addr` |
| CMD7 | `select_card` | `rca << 16` | R1/R1b | `busy` 为 1 时 R1b |
| CMD8 | `send_ext_csd` | 默认 0 | R1 | eMMC 读 512B EXT_CSD |
| CMD13 | `send_status` | `rca << 16`，低位含 `sqs/hpi` | R1 | 状态查询 |
| CMD16 | `set_blocklen` | `block_length` | R1 | 默认 512 |
| CMD23 | `set_block_count` | bit[15:0] 为 `number_of_blocks` | R1 | 多块读写前设置块数；默认 tag/context/forced 为 0 |

## 读写命令

| 命令 | 模板 | argument | 数据方向 | 块选择 |
| --- | --- | --- | --- | --- |
| CMD17 | `read_single_block` | `addr[31:0]` | read | SINGLE |
| CMD18 | `read_multiple_block` | `addr[31:0]` | read | MULTI |
| CMD24 | `write_block` | `addr[31:0]` | write | SINGLE |
| CMD25 | `write_multiple_block` | `addr[31:0]` | write | MULTI |

`rw_test_seq.addr` 应有确定默认值。外层 `rw_test_seq` 会把 `addr` 传给 `xfer_read_seq` / `xfer_write_seq`，再进入 CMD17/18/24/25。若外层未约束，CMD18/CMD25 的 argument 会随机。

## eMMC CMD6

`switch_command_request` 生成 eMMC CMD6 EXT_CSD 写：

- `argument[25:24] == access`
- `argument[23:16] == index`
- `argument[15:8] == value`
- `argument[2:0] == cmd_set`
- `resp == R1b`

常用派生：

| 模板 | EXT_CSD index | value 来源 | 用途 |
| --- | --- | --- | --- |
| `switch_bus_width` | 183 (`0xb7`) | `enhanced_strobe` 和 `bus_mode_selection` | 数据位宽、DDR/strobe |
| `switch_hs_timing` | 185 (`0xb9`) | `drive_strength` 和 `timing_interface` | 速度模式 |
| `switch_partition_config` | 179 (`0xb3`) | `boot_ack`、`boot_partition_enable`、`boot_partition_access` | 分区访问 |

默认分区配置全为 NO 时不能发送 `switch_partition_config`。否则会出现无效的 CMD6 `argument = 03b30000`。

## SD CMD6

`switch_func_command_request` 只在 SD card 分支生成：

- `cmd_index == 6`
- `argument[31] == mode`
- `argument[15:12]` 为电流限制
- `argument[11:8]` 为驱动强度
- `argument[7:4]` 为 command system
- `argument[3:0]` 为 access mode
- `data_present_sel == 1`
- 读取 64B function status

## SDIO CMD52/CMD53

| 命令 | 模板 | 关键字段 |
| --- | --- | --- |
| CMD52 | `io_rw_direct/*` | `argument[31]` 读写，`[30:28]` function，`[27]` RAW，`[25:9]` address，`[7:0]` write data |
| CMD53 | `io_rw_extended` | `argument[31]` 读写，`[30:28]` function，`[27]` block mode，`[26]` op code，`[25:9]` address，`[8:0]` count |

CMD53 的 `multi_blk_sel` 由 `block_mode/count` 推导：

- `block_mode == BLOCK && count != 1` 时为 MULTI
- 其他情况为 SINGLE
