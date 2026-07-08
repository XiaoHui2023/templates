# IO RW Direct Flow

## FN0 Block Size

`io_rw_direct_fn0_block_size_seq` 用 CMD52 配置 SDIO function block size。

| 字段 | 作用 |
| --- | --- |
| `function_number` | 目标 function，范围 1 到 7 |
| `block_length` | 16-bit block size |

过程：

1. CMD52 写 block size low byte，`cmd_request.lo_hi == 0`。
2. CMD52 写 block size high byte，`cmd_request.lo_hi == 1`。

关键点：

- 两次 CMD52 使用同一个 `block_length` 和 `function_number`。
- 该 flow 只配置 FN0 block size 寄存器，不执行 CMD53 数据传输。
- CMD53 的 block/byte mode、count、address 由 `xfer_base_seq.execute_sdio()` 约束。
