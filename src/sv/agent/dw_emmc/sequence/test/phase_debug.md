# Phase Debug Test

## 输入

| 字段 | 作用 |
| --- | --- |
| `addr` | 读写起始地址，默认 0 |
| `count` | 本轮读写块数，默认 2；SDSC 固定 1 |
| `block_size` | 每块字节数，默认 512 |
| `max_round_count` | 最大调试轮数，默认 64 |
| `dma_enable` / `dma_sel` | 数据搬运方式；仅 `enable_dma: true` 时生成 |
| `adma_des_addr` | ADMA 描述符地址；仅 `enable_dma: true` 时生成 |

## Callback

| 函数 | 作用 |
| --- | --- |
| `debug_write_phase(round, stop)` | 外部写调相。`round` 从 0 开始，`stop` 为 1 表示本轮后不再继续调试 |
| `debug_read_phase(round, stop)` | 外部读调相。`round` 从 0 开始，`stop` 为 1 表示本轮后不再继续调试 |
| `debug_dat_stb_phase(round, stop)` | 外部 DAT STB 调相。只在 eMMC 中使用 |
| `get_card_memory(addr, len, data, valid)` | 可选获取卡模型 memory。默认 `valid = 0` |

默认 callback 输出 `stop = 1`。未重载时只运行一轮。

## 流程

eMMC：

1. 初始化卡。
2. 切到 HS200 8-bit。
3. 循环调试写相位。
4. 写相位成功后循环调试读相位。
5. 读相位成功后切到 HS400 8-bit。
6. 循环调试 DAT STB。

SDCard / SDIO：

1. 初始化卡。
2. V1_8 时选择最高可用速度，优先级为 SDR104、SDR50、DDR50、SDR25、SDR12。
3. V3_3 时使用 HS。
4. 循环调试写相位。
5. 写相位成功后循环调试读相位。

## 写调相

1. 调用 `debug_write_phase(round, stop)`。
2. 执行一次写。
3. 写失败，记录原因并进入下一轮。
4. 写成功后更新 scoreboard。
5. 如果 `get_card_memory()` 返回有效数据，用 card memory 和 scoreboard 比较。
6. 没有有效 card memory 时，写命令完成即认为本轮写调相成功。

## 读调相

1. 调用 `debug_read_phase(round, stop)`。
2. 如果 `get_card_memory()` 返回有效数据，先用它同步 scoreboard。
3. 执行一次读。
4. 读失败或 scoreboard 比较失败，记录原因并进入下一轮。
5. 读成功并比较通过，当前调试阶段结束。

## DAT STB 调相

1. 调用 `debug_dat_stb_phase(round, stop)`。
2. 如果 `get_card_memory()` 返回有效数据，先用它同步 scoreboard。
3. 执行一次读。
4. 读失败或 scoreboard 比较失败，记录原因并进入下一轮。
5. 读成功并比较通过，当前调试阶段结束。

## 关键点

- 每轮失败不报 `UVM_ERROR`，只用 `UVM_LOW` 打印轮次和原因。
- 只有 callback 返回 `stop = 1` 且本轮失败时，才报最终 `UVM_FATAL`。
- 非最终失败轮会尝试 CMD/DAT 软复位，避免影响下一轮；mobile_storage 会跳过不存在的软件复位寄存器。
- 普通 `rw_test` 不打开非致命失败路径，原有 fatal 行为不变。
- 默认校验只使用 agent 自己的 scoreboard。需要直接对 SVT card memory 校验时，由外部重载 `get_card_memory()`。
