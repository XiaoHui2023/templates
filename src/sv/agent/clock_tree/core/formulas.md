# 计算公式

- **f** — 本节点输出频率
- **f_ref** — 前级节点频率
- **f_actual** — 寄存器编码对应的实际输出频率
- 单位 — Hz

## 分频频率与容差

| 参数 | 说明 |
| --- | --- |
| **f_hw** | 前级频率除以分频比后的整数商 |
| **epsilon** | 分频约束的相对容差 |

```text
f_hw = floor(f_ref / ratio)
floor(f_hw × (1 - epsilon)) <= f <= floor(f_hw × (1 + epsilon))
```

此范围用于分频约束，不改变寄存器对应的实际输出频率，也不代替测量误差范围。

## div

| 参数 | 说明 |
| --- | --- |
| **ratio** | 分频比，1～max_ratio |
| **max_ratio** | 节点允许的最大分频比 |
| **N** | **div** 寄存器写入值 |

```
f_actual = f_ref / ratio
N = ratio - 1
```

位宽为 **w** 的寄存器可编码 1～2^w 的分频比；节点的 **max_ratio** 还会进一步限制选择范围。

## div_r

固定分频，无寄存器。

| 参数 | 说明 |
| --- | --- |
| **ratio** | 固定分频比，大于 0 |

```
f_actual = f_ref / ratio
```

## clk_div_with_clken

| 参数 | 说明 |
| --- | --- |
| **code** | 四位寄存器值 |
| **ratio** | code 为 0～1、2～3、4～7、8～15 时，分别为 2、3、4、6 |

```text
f_clk_arm_core = f_ref
f_hclk = f_ref / ratio
f_hclken = f_hclk
```

## dto

| 参数 | 说明 |
| --- | --- |
| **ratio** | 分频比，大于 0 且不超过 2^25 |
| **step** | **step** 寄存器写入值；旁通时为 0，分频时为 1～2^25−1 |
| **bypass** | 旁通开关；**ratio** 为 1 时写 1，否则写 0 |

分频比大于 1 时：

```
step = floor(2^25 / ratio)
f_actual = f_ref × step / 2^25
```

**ratio** 为 1 时旁通：**bypass**=1，**step**=0，**load**=1。

## pll

| 参数 | 说明 |
| --- | --- |
| **f** | 目标输出频率 |
| **f_ref** | 参考前级节点频率 |

由 **f_ref** 与 **f** 反算下列分频系数。

### tci

| 参数 | 说明 |
| --- | --- |
| **clkf** | 反馈分频，整数 |
| **clkr** | 参考分频，固定 1 |
| **clkod** | 输出分频，固定 1 |
| **bwadj** | 带宽调节，等于 **clkf** |

```
clkf = floor(f / f_ref)
```

输出近似 **f_ref × clkf**。

### sc

| 参数 | 说明 |
| --- | --- |
| **f_actual** | 由系数算出的输出频率 |
| **f_pfd** | 鉴相频率 |
| **f_vco** | VCO 频率 |
| **fbdiv** | 反馈分频，**fbdiv_min**～**fbdiv_max** |
| **refdiv** | 参考分频，1～63 |
| **postdiv1** | 后分频 1，1～7 |
| **postdiv2** | 后分频 2，1～7 |
| **fbdiv_min** | **fbdiv** 下限 |
| **fbdiv_max** | **fbdiv** 上限 |
| **f_pfd_min** | 鉴相频率下限 |
| **f_vco_min** | VCO 频率下限 |
| **f_vco_max** | VCO 频率上限 |

```
f_pfd = f_ref / refdiv
f_vco = f_pfd × fbdiv
f_actual = f_vco / postdiv1 / postdiv2
```

仅保留 **f_pfd ≥ f_pfd_min**、**f_vco_min ≤ f_vco ≤ f_vco_max** 的组合。每组 **refdiv**、**postdiv1**、**postdiv2** 检查合法区间内最接近理想值的两个 **fbdiv**，按精确输出误差选取全局最优解；误差相同时优先较高鉴相频率，再优先较高 VCO 频率。

最优合法解的相对误差超过允许值，或不存在合法组合时，在写寄存器前报错。

### inno

| 参数 | 说明 |
| --- | --- |
| **f_actual** | 由系数算出的输出频率 |
| **fbdiv** | 反馈分频，绑定位宽内四舍五入取整，两路共用；不得为 0～7 或 11 |
| **refdiv** | 参考分频，1～63；两路共用 |
| **postdiv1** | 后分频 1，1～7；每路独立 |
| **postdiv2** | 后分频 2，1～7；每路独立 |
| **postdiv1_reg** | **postdiv1** 寄存器写入值，0～6；每路独立 |
| **postdiv2_reg** | **postdiv2** 寄存器写入值，0～6；每路独立 |

```
f_actual = f_ref × fbdiv / refdiv / postdiv1 / postdiv2
```

**postdiv1** 为 **postdiv1_reg + 1**；**postdiv2** 为 **postdiv2_reg + 1**。分频为 1 时写入 0。

**fbdiv**、**refdiv** 两路共用；每路各有 **postdiv1**、**postdiv2**。

在合法组合中使 **f_actual** 与 **f** 绝对误差最小。先视 **postdiv1**、**postdiv2** 均为 1，在 **refdiv** 1～63 与合法 **fbdiv** 范围内搜共用系数；**fbdiv** 跳过 0～7 与 11；再固定已定的 **fbdiv**、**refdiv**，在 **postdiv1**、**postdiv2** 各 1～7 内为该路搜后级分频。

### dw

| 参数 | 说明 |
| --- | --- |
| **f_actual** | 由系数算出的输出频率 |
| **fbdiv** | 反馈分频，1～1023，四舍五入取整 |
| **p** | 后分频索引，0～7 |
| **postdiv** | **p + 1** |

```text
f_actual = f_ref × fbdiv / postdiv
```

在 **p** 为 0～7 范围内搜索，使 **f_actual** 与 **f** 绝对误差最小。

## 测量相位

| 参数 | 说明 |
| --- | --- |
| **t_rise** | 当前上升沿时刻 |
| **t_ref** | 本次测量第一个上升沿时刻 |
| **T** | 当前测得周期 |
| **phase_frac** | 归一化相位，取值 0 以上且小于 1 |

```
phase_frac = fmod(t_rise - t_ref, T) / T
```

这是本路时钟相对自身首个上升沿的位置，不是两路时钟的相位差。
