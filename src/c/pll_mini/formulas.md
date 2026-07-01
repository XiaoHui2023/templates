# 寄存器计算公式

- **f_ref**：前级参考频率。
- **f_out**：目标输出频率。
- **ratio**：分频比。
- **step**：DTO 寄存器写入值。
- **tol**：允许相对频率偏差。

## div

| 参数 | 说明 |
| --- | --- |
| **f_ref** | 前级频率 |
| **ratio** | 分频比，普通 div 允许 1 到 64 |
| **f_hw** | 硬件整数分频后的频率 |

```text
f_hw = f_ref // ratio
rem = f_ref % ratio
```

`f_out` 与 `f_hw` 按容差比较。寄存器写入值为：

```text
N = ratio - 1
```

## dto

| 参数 | 说明 |
| --- | --- |
| **ratio** | DTO 分频比，允许 2 到 2^25 |
| **step** | DTO 步进寄存器值 |

```text
step = (2^25) // ratio
```

`step` 必须在 1 到 `2^25 - 1` 内。`ratio=1` 会得到 `step=2^25`，不是合法寄存器值。

## TCI PLL

| 参数 | 说明 |
| --- | --- |
| **clkf** | 倍频系数 |

```text
f_out = f_ref * clkf
```

寄存器写入使用 `clkf`，`bwadj` 与 `clkf` 相同，`clkr` 和 `clkod` 固定为 1。

## SC PLL

| 参数 | 说明 |
| --- | --- |
| **fbdiv** | 反馈分频系数 |
| **refdiv** | 参考分频系数 |
| **postdiv1** | 后级分频 1 |
| **postdiv2** | 后级分频 2 |

```text
f_hw = (f_ref * fbdiv) // (refdiv * postdiv1 * postdiv2)
```

`f_out` 与 `f_hw` 按容差比较。`fbdiv` 使用配置允许的上下限。

## DW PLL

| 参数 | 说明 |
| --- | --- |
| **fbdiv** | 反馈分频系数 |
| **p** | P 分频寄存器语义 |

```text
f_hw = (f_ref * fbdiv) // (p + 1)
```

`f_out` 与 `f_hw` 按容差比较。

## INNO PLL

| 参数 | 说明 |
| --- | --- |
| **fbdiv** | 反馈分频系数 |
| **refdiv** | 参考分频系数 |
| **postdiv1_g** | 输出组 **g** 的后级分频 1 |
| **postdiv2_g** | 输出组 **g** 的后级分频 2 |

```text
f_hw_g = (f_ref * fbdiv) // (refdiv * postdiv1_g * postdiv2_g)
```

只对有效输出组比较 `f_out_g`。未被下游使用的输出组不参与寄存器系数匹配。
