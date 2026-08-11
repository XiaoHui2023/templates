# Sequence

sequence 使用 operation、flow、test 三层命名。operation 按子目录聚合，每个子目录固定包含 `req.sv`、`rsp.sv`、`op.sv`。flow 和 test 使用扁平 sequence 文件，输入字段直接放在 sequence 类里。不从外部注入 dependency sequence。

## 初始化

eMMC 初始化：

1. `frequence_set_operation_seq`，目标 400000Hz
2. `power_up_operation_seq`，默认不执行软复位；`enable_soft_reset == 1` 时先执行 CMD/DAT 软复位
3. `check_clock_frequence_test_seq`
4. CMD0 `go_idle_state`
5. CMD1 `send_op_cond`，当前约束 `ocr == 32'h40ff8080`
6. CMD2 `all_send_cid`
7. CMD3 `set_relative_addr`
8. `pre_switch_yield`
9. CMD7 `select_card`
10. `frequence_set_operation_seq`，目标 `boot_cfg.frequence_legacy`
11. `post_switch_yield`

`ctx.has_initialized` 置 1 后，后续测试不重复初始化。

## 总线切换

eMMC `switch_bus_seq`：

1. 频率降到 6000000Hz
2. DDR/HS400 目标模式先发过渡 CMD6，把 HS_TIMING 设为 HIGH_SPEED_SDR
3. CMD6 写 BUS_WIDTH
4. CMD6 写 HS_TIMING 到目标速度
5. 按当前 `ctx.bus_speed_mode_cur` 设置目标频率

HS400 + 8bit 的 CMD6 期望序列：

| 次序 | 作用 | argument |
| --- | --- | --- |
| 1 | HS_TIMING -> HIGH_SPEED_SDR | `03b90100` |
| 2 | BUS_WIDTH -> 8bit DDR | `03b70600` |
| 3 | HS_TIMING -> HS400 | `03b90300` |

不应出现 `03b30000`。该值是 PARTITION_CONFIG 的 no-op 写入，只在分区配置非默认时发送。

## 读写测试

`rw_test_seq` 默认行为：

- `addr == 0`
- `rd == 1`
- `wr == 1`
- `rd_multi_block_count == 2`
- `wr_multi_block_count == 2`
- eMMC 默认 `rd_block_size == 512`、`wr_block_size == 512`
- 默认分区配置为 NO，不发分区 CMD6

默认 `rd_single/wr_single` 二选一，`rd_multi/wr_multi` 二选一。指定精确路径时必须用 `cst_case` 或 `uvm_do_with` 约束读写方向和 single/multi。

执行段：

1. 初始化缺失时运行 `initial_seq`
2. 运行 `switch_bus_seq`
3. eMMC 分区配置非默认时运行 `switch_partition_config_command_seq`；SD/SDIO 不生成该命令
4. 按 `rd_single/rd_multi/wr_single/wr_multi/abort` 运行读写 transfer
5. 写操作完成后向 scoreboard 发送 payload，更新 expected memory
6. 读操作完成后向 scoreboard 发送 payload，自动与 expected memory 比较

`rw_test_seq` 默认先执行 write，再执行 read。scoreboard 可以先加载与 card 相同的初始文件；写操作会改变 expected memory；后续读操作必须对比写后的 expected memory，而不是旧 card VIP 内存。

只读测试需要先通过 `agent.scb` 加载 scoreboard 初始内容。

指定可复现只读路径时约束这些字段：

```systemverilog
rd == 1;
wr == 0;
rd_multi == 1;
rd_single == 0;
addr == 0;
rd_multi_block_count == 2;
```

## 多块读

`xfer_read_seq` 的多块路径：

1. `enable_dma: true` 且使用 ADMA 时，`xfer_base_seq.body` 写 ADMA 描述符
2. `xfer_base_seq.body` 设置 block length；DDR/HS400 模式跳过 CMD16
3. `xfer_read_seq.execute_command`
4. CMD23 `set_block_count`
5. CMD18 `read_multiple_block`
6. 等待传输完成
7. PIO 从 buffer 读取；DMA 从 memory 读取

CMD23 只由读/写派生序列在需要多块时发送。基类 body 不发送 CMD23。

HS400 多块读已测试通过的关键结果：

- 切总线 CMD6：`03b90100`、`03b70600`、`03b90300`
- CMD23：`00000002`
- CMD18：`00000000`
- 无 CMD6 `03b30000`

## 多块写

`xfer_write_seq` 的多块路径：

1. `enable_dma: true` 且使用 ADMA 时，`xfer_base_seq.body` 写 ADMA 描述符
2. `xfer_base_seq.body` 设置 block length；DDR/HS400 模式跳过 CMD16
3. `xfer_write_seq.execute_command`
4. 非 abort 时 CMD23 `set_block_count`
5. CMD25 `write_multiple_block`
6. 等待传输完成

abort 写路径通过 `AUTO_CMD12_ENABLED` 停止，不发送 CMD23。

## PIO 数据搬运

PIO read：

1. 等 `cmd_complete`
2. 等每块 `buf_rd_ready`
3. 读 `BUF_DATA_R`
4. 等 `xfer_complete`
5. 去掉尾部补齐字节

PIO write：

1. 写命令前不预写 memory
2. 等 `cmd_complete`
3. 等每块 `buf_wr_ready`
4. 写 `BUF_DATA_R`
5. 等 `xfer_complete`

## DMA 数据搬运

仅 `enable_dma: true` 时生成。

DMA write：

1. `init_memory()` 在命令前把 `cmd_request.wdata` 写入 memory
2. SDMA 使用数据 buffer 地址；ADMA 使用描述符地址 `cmd_request.dma_addr[31:0]`
3. `mobile_storage` 使用 IDMAC 描述符链表：`DBADDR_R` 写描述符链表地址，真实数据 buffer 地址在描述符里，随后向 `POLDMD_R` 写 `32'h1`；`0x84` 是 `POLDMD_R` 地址
4. 命令发出后只等 `xfer_complete`

DMA read：

1. 命令前不初始化 memory
2. 等 `xfer_complete`
3. 从 memory 读回数据

ADMA 描述符只在 `dma_sel inside {ADMA2, ADMA2_3}` 时写入。描述符地址不能与数据区重叠。

## 中断等待

命令流程等待：

- `wait_cmd_complete()` 等 `cmd_complete`
- 读写数据后等 `xfer_complete`
- PIO read 等 `buf_rd_ready`
- PIO write 等 `buf_wr_ready`

等待请求携带 `chk_err_request`。错误检查字段不应散落在具体命令序列里。

## clock 检查

Python 输入 `monitored_clocks[].enable == true` 的 clock 才生成端口、配置字段和检查调用。默认只生成 `hclk`，按 `presence` 检查。

SV 不生成 clock 检查开关。monitor interface 对每个已生成 clock 先用 `$isunknown(clk)` 判断是否连接；未连接或 X/Z 时跳过，已连接时按 `presence`、`relation` 或 `frequency` 类型检查，失败时报 `uvm_fatal`。

## 关键检查

- `rw_test_seq.addr` 是 CMD17/18/24/25 argument 的源头。
- `switch_partition_config` 默认 NO 时不能上总线。
- `set_block_count()` 只能有一个流程 owner。
- `resp_type_select` 从 `cmd_request.access_request` 访问。
- clock 字段只来自 Python 启用生成的 `monitored_clocks`，调用方不能硬编码未生成字段。
- `uvm_do_with` 必须带内嵌约束；无约束调用用 `uvm_do`。
- 内嵌约束用 `==`，不能写赋值 `=`。
