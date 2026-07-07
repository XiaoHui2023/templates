# DW eMMC 启动参考

## HS400 多块读参考

输入约束：

```systemverilog
data_width == 8;
bus_speed_mode == HS400;
rd == 1;
rd_multi == 1;
rd_single == 0;
wr == 0;
addr == 0;
rd_multi_block_count == 2;
rd_block_size == 512;
dma_enable == 0;
boot_partition_enable == BOOT_PARTITION_ENABLE_NO;
boot_partition_access == BOOT_PARTITION_ACCESS_NO;
```

关键命令：

| 阶段 | 命令 | argument | 说明 |
| --- | --- | --- | --- |
| bus switch | CMD6 | `03b90100` | HS_TIMING -> HIGH_SPEED_SDR |
| bus switch | CMD6 | `03b70600` | BUS_WIDTH -> 8bit DDR |
| bus switch | CMD6 | `03b90300` | HS_TIMING -> HS400 |
| read setup | CMD23 | `00000002` | 读取 2 块 |
| read | CMD18 | `00000000` | 从地址 0 读多块 |

不应出现：

| 命令 | argument | 原因 |
| --- | --- | --- |
| CMD6 | `03b30000` | 默认 PARTITION_CONFIG no-op 写入 |
| CMD18 | 随机值 | 外层 `rw_test_seq.addr` 未固定 |

## 排查口径

- CMD6 数量超过预期时，先查 `switch_bus_seq` 和 `switch_partition_config_command_seq`。
- CMD18/CMD25 argument 随机时，先查外层 test 的 `addr`，不是只查 `xfer_base_seq.addr`。
- CMD23 重复时，查 `xfer_base_seq.body` 和读写派生序列是否同时调用 `set_block_count()`。
- response 类型异常时，查 `cmd_req.access_req.resp_type_select`。

## 正常 no-op

这些默认值不应产生额外命令：

- `boot_partition_enable == BOOT_PARTITION_ENABLE_NO`
- `boot_partition_access == BOOT_PARTITION_ACCESS_NO`
- volatile clock 的 `frequence_*` 检查字段

这些默认值可以产生命令：

- 多块读写的 `count > 1` 会产生 CMD23
- 非 DDR 的 eMMC/SD 传输会按需要产生 CMD16
