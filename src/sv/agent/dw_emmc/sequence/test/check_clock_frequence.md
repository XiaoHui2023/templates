# Check Clock Frequence Test

## 输入

| 字段 | 作用 |
| --- | --- |
| `should` | 是否启用检查，默认来自 `settings.chk_clk_cfg.should` |
| `should_<clk>` | 是否检查该非 volatile clock |
| `frequence_<clk>` | 期望频率，单位 Hz |
| `tolerance_<clk>` | 允许误差，百分比 |

## 流程

1. `should == 0` 时直接返回。
2. 遍历非 volatile clock。
3. 对启用检查的 clock 调用 `settings.vif.monitor_if.check_<clk>_frequence()`。
4. timeout 或频率超差时报 `uvm_fatal`。

volatile clock 不生成输入字段，也不能被调用方约束。
