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

在顶层 interface 连接 `phase_tx_ref` / `phase_tx_clk` 和 `phase_rx_ref` / `phase_rx_clk`。每对分别是连续运行的目标相位参考时钟和实际可调时钟，必须同频。只执行一个方向时，只需连接对应的一对。参考时钟要反映项目期望的采样时序，不能随意接同频信号。

在已注册的 callback 中重写 `adjust_tx_phase` / `adjust_rx_phase`。输入 `shift_fs` 是相对当前相位的调整量，正值增加延迟，负值使边沿提前。回调负责换算档位、配置项目寄存器并等待生效；成功才返回 `applied = 1`，不能调整时保持原设置。

| 速率模式 | 写 | 读 |
| --- | --- | --- |
| HS200 | 测 TX 上升沿 | 测 RX 上升沿 |
| HS400 | 测 TX 双边沿 | 传输前不测 DS，不修改 RX |

默认速度为 HS400；需要同时测写和读时，通过现有启动配置选择 HS200。

非上述模式、未连接、时钟不稳定或回调无法调整时报告 `CLOCK_PHASE`，继续原读写。正常读写及 scoreboard 比较仍是最终验证，时钟对齐不等同于数据眼校准。
