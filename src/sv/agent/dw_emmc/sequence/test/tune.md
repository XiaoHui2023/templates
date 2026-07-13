# Tune Test

## 输入

| 字段 | 作用 |
| --- | --- |
| `bus_speed_mode` | 调谐前切换到的速度模式 |
| `data_width` | 调谐前切换到的数据位宽 |

## 流程

1. 未初始化时运行 `initial_seq`。
2. 运行 `switch_bus_seq` 切到目标位宽和速度。
3. 对 phase `0..15` 逐个运行 `tune_seq`。
4. 调谐后运行一次多块写再多块读，验证数据面并触发 scoreboard 比较。

该测试要求 `settings.boot_cfg.voltage == V1_8`。
