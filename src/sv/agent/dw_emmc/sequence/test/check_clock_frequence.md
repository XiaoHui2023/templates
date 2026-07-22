# Check Clock Frequence Test

## 输入

| 字段 | 作用 |
| --- | --- |
| `min_frequence_<clk>` | `presence` / `relation` 检查使用的最小频率，单位 Hz |
| `frequence_<clk>` | `frequency` 检查使用的期望频率，单位 Hz |
| `tolerance_<clk>` | `frequency` 检查使用的容差，百分比 |
| `relation_tolerance_<clk>` | `relation` 中 `==` 比较使用的容差，百分比 |

## 流程

1. 遍历 Python 配置中启用生成的 clock。
2. `presence` 检查测量该 clock，要求不超时且频率不低于 `min_frequence_<clk>`。
3. `frequency` 检查测量该 clock，要求频率在 `frequence_<clk>` 和 `tolerance_<clk>` 范围内。
4. `relation` 检查测量两个 clock，要求满足 Python 生成的 `relation_operator`。
5. monitor interface 用 `$isunknown(clk)` 判断端口是否连接；未连接或 X/Z 时跳过。
6. 已连接但 timeout、低于最小频率、超出容差或关系不成立时报 `uvm_fatal`。

默认只生成 `hclk`，按 `presence` 检查。额外 clock 需要在 `models.py` 输入的 `monitored_clocks` 中设置 `enable: true`。
