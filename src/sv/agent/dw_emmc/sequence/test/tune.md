# Tune Test

## 输入

| 字段 | 作用 |
| --- | --- |
| `bus_speed_mode` | 调谐前切换到的速度模式；未指定时使用最高速 |
| `data_width` | 调谐前切换到的数据位宽；未指定时使用最大位宽 |

## 流程

1. 未初始化时运行 `initial_seq`。
2. 运行 `switch_bus_seq` 切到目标位宽和速度。
3. 对 phase `0..15` 逐个运行 `tune_seq`。
4. 调谐后运行一次多块写再多块读，验证数据面并触发 scoreboard 比较。

该测试要求 `settings.boot_cfg.voltage == V1_8`。

## 关键点

- 该测试不是只发送 tuning block；phase 扫描后必须用实际读写验证数据面。
- 默认目标为最高速和最大位宽：eMMC 为 `HS400/8-bit`；SD/SDIO 按能力位选择 `SDR104`、`DDR50`、`SDR50`、`SDR25`、`SDR12` 中最高可用项，位宽为 4-bit。
- scoreboard 比较由调谐后的 `rw_test_seq` 完成。
