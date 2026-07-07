# DW eMMC 执行流程

## 初始化

eMMC 初始化：

1. `assert_connection_test_seq`
2. `frequence_set_dependency_seq`，目标 400000Hz，不检查频率
3. `power_up_request_seq`
4. `check_clock_frequence_test_seq`
5. CMD0 `go_idle_state`
6. CMD1 `send_op_cond`，当前约束 `ocr == 32'h40ff8080`
7. CMD2 `all_send_cid`
8. CMD3 `set_relative_addr`
9. `pre_switch_yield`
10. CMD7 `select_card`
11. `frequence_set_dependency_seq`，目标 `boot_cfg.frequence_legacy`
12. `post_switch_yield`

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
- `rd_multi_block_count == 2`
- `wr_multi_block_count == 2`
- eMMC 默认 `rd_block_size == 512`、`wr_block_size == 512`
- 默认分区配置为 NO，不发分区 CMD6

执行段：

1. 初始化缺失时运行 `initial_seq`
2. 运行 `switch_bus_seq`
3. 分区配置非默认时运行 `switch_partition_config_command_seq`
4. 按 `rd_single/rd_multi/wr_single/wr_multi/abort` 运行读写 transfer
5. `should_compare` 为 1 时对比 card memory

## 多块读

`xfer_read_seq` 的多块路径：

1. `xfer_base_seq.body` 写 ADMA 描述符
2. `xfer_base_seq.body` 设置 block length；DDR 模式跳过 CMD16
3. `xfer_read_seq.execute_command`
4. CMD23 `set_block_count`
5. CMD18 `read_multiple_block`
6. 等待传输完成
7. 读取 buffer 或 DMA memory

CMD23 只由读/写派生序列在需要多块时发送。基类 body 不发送 CMD23。

## 多块写

`xfer_write_seq` 的多块路径：

1. `xfer_base_seq.body` 写 ADMA 描述符
2. `xfer_base_seq.body` 设置 block length；DDR 模式跳过 CMD16
3. `xfer_write_seq.execute_command`
4. 非 abort 时 CMD23 `set_block_count`
5. CMD25 `write_multiple_block`
6. 等待传输完成

abort 写路径通过 `AUTO_CMD12_ENABLED` 停止，不发送 CMD23。

## 关键检查

- `rw_test_seq.addr` 是 CMD17/18/24/25 argument 的源头。
- `switch_partition_config` 默认 NO 时不能上总线。
- `set_block_count()` 只能有一个流程 owner。
- `resp_type_select` 从 `cmd_req.access_req` 访问。
- volatile clock 不生成 `frequence_*` 字段，测试平台不能硬编码这些字段。
