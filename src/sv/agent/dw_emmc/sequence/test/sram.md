# SRAM Test

## 输入

| 字段 | 作用 |
| --- | --- |
| `block_count` | 读取块数，默认由 `settings.boot_cfg.sram_size / block_size` 推导 |
| `block_size` | 块大小，按 SRAM 大小优先选择 2048、1024、512 |

## 流程

1. 运行只读多块 `rw_test_seq`。
2. `rd_blocking == 1`。
3. `wr == 0`，不修改 scoreboard expected memory。

运行前需要通过 `agent.scb` 加载与 card/SRAM 一致的初始镜像。
