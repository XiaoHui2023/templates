# Check Clock Frequence Test

## 输入

| 字段 | 作用 |
| --- | --- |
| `frequence_<clk>` | 期望频率，单位 Hz |
| `tolerance_<clk>` | 允许误差，百分比 |

## 流程

1. 遍历 Python 配置中启用生成的 clock。
2. 调用 `settings.vif.monitor_if.check_<clk>_frequence()`。
3. monitor interface 用 `$isunknown(clk)` 判断端口是否连接。
4. 未连接或 X/Z 时跳过；已连接时测频。
5. timeout 或频率超差时报 `uvm_fatal`。

默认只生成 `hclk`。额外 clock 需要在 `models.py` 输入的 `monitored_clocks` 中设置 `enable: true`。
