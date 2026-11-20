# 寄存器计算公式

`f_ref` 为前级频率，`f_hw` 为硬件输出频率，单位均为 Hz。`//` 表示整数除法；目标频率与计算结果按 `period_tolerance` 比较。

| 节点 | 频率或编码公式 | 参数范围与写入 |
| --- | --- | --- |
| div | `f_hw = f_ref // ratio` | 可编程比值为 1～64，写入 `ratio - 1`。 |
| DTO | `step = (2^25) // ratio`，`f_hw = f_ref // ratio` | 可编程比值为 2～`2^25`，`step` 为 1～`2^25 - 1`。 |
| TCI PLL | `f_hw = f_ref * clkf` | `bwadj = clkf`，`clkr = clkod = 1`。 |
| SC PLL | `f_hw = (f_ref * fbdiv) // (refdiv * postdiv1 * postdiv2)` | `fbdiv` 受配置上下限约束。 |
| DW PLL | `f_hw = (f_ref * fbdiv) // (p + 1)` | `p` 使用寄存器编码值。 |
| INNO PLL | `f_hw[g] = (f_ref * fbdiv) // (refdiv * postdiv1[g] * postdiv2[g])` | 每路后级实际分频为 1～7，寄存器写入实际值减 1。 |
| clk_div_with_clken | `core = f_ref`，`hclk = hclken = f_ref // ratio` | 比值 2、3、4、6 分别编码为 0、2、4、8。 |

DTO 的固定 `ratio` 上限为 64；可编程 `init_ratio` 与求解值使用表中的硬件范围。`ratio=1` 会得到越界的 `step=2^25`，不能用于 DTO。

INNO 两路共用 `refdiv` 和 `fbdiv`，分别使用自己的 `postdiv1`、`postdiv2`；只有有效输出组参与频率拟合。
