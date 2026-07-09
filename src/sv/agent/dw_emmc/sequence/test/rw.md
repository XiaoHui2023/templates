# RW Test

## 输入

| 字段 | 作用 |
| --- | --- |
| `addr` | CMD17/18/24/25 argument 来源，默认 0 |
| `rd` / `wr` | 是否执行读、写路径，默认都执行 |
| `rd_single` / `rd_multi` | 单块读或多块读 |
| `wr_single` / `wr_multi` | 单块写或多块写 |
| `rd_multi_block_count` / `wr_multi_block_count` | 多块读写块数，默认 2 |
| `data_width` / `bus_speed_mode` | 传输前切换的总线位宽和速度 |
| `dma_enable` / `dma_sel` | 数据搬运方式 |
| `should_compare` | 读数据是否与 scoreboard 比较 |
| `wp` | 写保护场景；写命令不更新 scoreboard expected memory |

## 流程

1. 未初始化时运行 `initial_seq`。
2. 运行 `switch_bus_seq`。
3. eMMC 分区配置非默认时发送 `switch_partition_config_command_seq`；SD/SDIO 不生成该命令。
4. 按写路径先更新 scoreboard expected memory。
5. 按读路径从 DUT 取数据并与 scoreboard memory 比较。

默认执行多块写，再执行多块读。只读场景需要先通过 `agent.scb` 加载初始镜像。
