# RW Test

## 输入

| 字段 | 作用 |
| --- | --- |
| `addr` | CMD17/18/24/25 argument 来源，默认 0 |
| `rd` / `wr` | 启用读、写，默认都打开。启用读后至少选择单块读或多块读 |
| `rd_single` / `rd_multi` | 单块读或多块读 |
| `wr_single` / `wr_multi` | 单块写或多块写 |
| `rd_multi_block_count` / `wr_multi_block_count` | 多块读写块数，默认 1 |
| `rd_blocking` | PIO 阻塞读模式，不选择读操作；MSHC 默认 0，mobile_storage SDIO 默认 1 |
| `data_width` / `bus_speed_mode` | 传输前切换的总线位宽和速度 |
| `dma_enable` / `dma_sel` | 数据搬运方式；仅 `enable_dma: true` 时生成 |
| `should_compare` | 是否比较读数据；默认仅同时读写时打开 |
| `wp` | 写保护场景；写命令不更新 scoreboard expected memory |

## 流程

未初始化先执行 `initial_seq`，再执行 `switch_bus_seq`。eMMC 分区配置非默认时发送 `switch_partition_config_command_seq`。写完成后记录期望数据；读完成后按 `should_compare` 决定是否比较。

默认执行单块写，再执行单块读并比较。只写、只读默认不比较；需要只读比较时显式约束 `should_compare == 1`。
