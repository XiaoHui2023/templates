# RW Test

## 输入

| 字段 | 作用 |
| --- | --- |
| `addr` | CMD17/18/24/25 argument 来源，默认 0 |
| `rd` / `wr` | 是否执行读、写路径，默认都执行 |
| `rd_single` / `rd_multi` | 单块读或多块读 |
| `wr_single` / `wr_multi` | 单块写或多块写 |
| `rd_multi_block_count` / `wr_multi_block_count` | 多块读写块数，默认 1 |
| `rd_blocking` | 读数据搬运顺序 |
| `data_width` / `bus_speed_mode` | 传输前切换的总线位宽和速度 |
| `dma_enable` / `dma_sel` | 数据搬运方式；仅 `enable_dma: true` 时生成 |
| `should_compare` | 是否比较读数据；默认仅同时读写时打开 |
| `wp` | 写保护场景；写命令不更新 scoreboard expected memory |

## 流程

1. 未初始化时运行 `initial_seq`。
2. 运行 `switch_bus_seq`。
3. eMMC 分区配置非默认时发送 `switch_partition_config_command_seq`；SD/SDIO 不生成该命令。
4. 写路径完成后更新 scoreboard expected memory。
5. 读路径完成后按 `should_compare` 决定是否与 scoreboard memory 比较。

默认执行单块写，再执行单块读并比较。只写、只读默认不比较；需要只读比较时显式约束 `should_compare == 1`。

## 读顺序

- MSHC 默认 `rd_blocking == 0`，先按 `BUF_RD_READY` 读走 controller buffer，再等待传输完成。
- mobile_storage SDIO 默认 `rd_blocking == 1`，先等 DTO，再读取 FIFO。
- 单块读和多块读都要把 `rd_blocking` 传入 xfer read。
