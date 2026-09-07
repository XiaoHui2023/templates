# Data

## base_data

| 成员 / 函数 | 说明 |
| --- | --- |
| `sizeof` | `unpack()` 后的字节数 |
| `unpack()` | 按 little-endian pack 结果转为 byte 队列 |
| `pre_randomize()` | 更新 `sizeof` |

## adma_des_data

仅 `enable_dma: true` 且 `controller_ip: mshc` 时生成。

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

## idmac_descriptor_data

仅 `enable_dma: true` 且 `controller_ip: mobile_storage` 时生成。

| 字段 | 说明 |
| --- | --- |
| `descriptor_addr` | IDMAC 描述符链表地址，写入 `DBADDR_R` |
| `data_addr` | DMA 数据 buffer 地址 |
| `next_descriptor_addr` | 下一描述符地址 |
| `own` | DES0 bit[31] |
| `end_of_ring` | DES0 bit[5] |
| `second_address_chained` | DES0 bit[4] |
| `first` | DES0 bit[3] |
| `last` | DES0 bit[2] |
| `dint` | DES0 bit[1] |
| `dir` | DES0 bit[0] |
| `buf1_size` | DES1 bit[12:0]，buffer1 字节数 |
| `buf2_size` | DES1 bit[25:13]，buffer2 字节数 |

单描述符默认：`own == 1`、`first == 1`、`last == 1`、`end_of_ring == 0`、`second_address_chained == 0`、`dint == 0`、`buf2_size == 0`。

512B 写传输默认描述符：

| Word | 值 |
| --- | --- |
| DES0 | `32'h8000_000c` |
| DES1 | `32'h0000_0200` |
| DES2 | 数据 buffer 地址 |
| DES3 | 下一描述符地址 |
