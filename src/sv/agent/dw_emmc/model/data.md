# Data

## base_data

| 成员 / 函数 | 说明 |
| --- | --- |
| `sizeof` | `unpack()` 后的字节数 |
| `unpack()` | 按 little-endian pack 结果转为 byte 队列 |
| `pre_randomize()` | 更新 `sizeof` |

## adma_des_data

仅 `enable_dma: true` 时生成。

| 字段 | 说明 |
| --- | --- |
| `cmd_addr` | ADMA 描述符写入地址 |
| `real_addr` | DMA 数据实际地址 |
| `attr_valid` | 描述符有效位 |
| `attr_end` | 描述符结束位 |
| `attr_int` | 描述符中断位 |
| `attr_act0` / `attr_act1` / `attr_act2` | ADMA action |
| `len_upper` / `len_lower` | 传输长度 |

基础默认值：`attr_* == 0`、`len_upper == 0`、`len_lower == 0`。

`xfer_base_seq` 在 ADMA2/ADMA2_3 传输中会覆盖为单描述符 transfer：`attr_valid == 1`、`attr_end == 1`、`attr_act1 == 1`、`len == count * size`、`real_addr == addr`。
