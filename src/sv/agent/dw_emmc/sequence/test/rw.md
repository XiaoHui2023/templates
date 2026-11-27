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
| `auto_clock_phase` | eMMC 专用。默认关闭，通过 `rw_test(.auto_clock_phase(1))` 开启 |

## 流程

未初始化先执行 `initial_seq`，再执行 `switch_bus_seq`。eMMC 分区配置非默认时发送 `switch_partition_config_command_seq`。写完成后记录期望数据；读完成后按 `should_compare` 决定是否比较。

默认执行单块写，再执行单块读并比较。只写、只读默认不比较；需要只读比较时显式约束 `should_compare == 1`。

## 自动调相

1. 将同一根卡时钟的芯片输出点接到 `link_chip_clk`，卡输入点接到 `link_card_clk`。不连接 DAT 或 DS，不使用 `force`。
2. 设置 `agent.settings.max_link_delay_ps` 为项目模型允许的最大单程传播延迟；该值必须小于测量窗口内相邻 CLK 边沿的最小间隔，避免把不同周期的边沿配对。
3. 在已注册的总 callback 中重写 `apply_link_phase`。切速后、第一笔读写前调用一次。输入为当前速度模式、实测周期（fs）、实测单程延迟的相位（度）和按对称假设估算的往返相位（度）。

相位换算为 `360 × 单程延迟 / 周期`，往返估算为单程的两倍，不按 360° 回绕。比如 200 MHz、350 ps 单程时，分别为 25.2° 和 50.4°。回调按芯片定义统一配置各时钟；传入的是传播相位，不是所有寄存器都要写入的相同修正量。只在整组设置生效后返回 `applied = 1`，不支持时保持原设置。

只有模型中返程传播确与出程相等时，往返估算才成立；它不包括卡内部响应时间、DAT/DS 偏斜，也不替代 CMD21 tuning。未连接、停钟、边沿无法配对或回调未应用时报告 `CLOCK_PHASE`，继续原读写。
