# 计算公式

- **f** — 本节点输出频率
- **f_ref** — 前级节点频率
- 单位 — Hz

## div

| 参数 | 说明 |
| --- | --- |
| **f** | 本节点输出频率 |
| **f_ref** | 前级节点频率 |
| **ratio** | 分频比，允许 1～64 |
| **N** | **div** 寄存器写入值 |

```
f_hw = f_ref / ratio
```

整数除法，**f_hw** 为寄存器按 **ratio** 配置后硅片输出频率。

model 里 **\_resolved_freq** 相对 **f_hw** 允许整数偏差，与 **check_measure** 频率容差同一 **period_tolerance**；由 **div_freq_tol_num**、**div_freq_tol_den** 在配置渲染时算出 **div_freq_tol_lo**、**div_freq_tol_hi**，默认 **period_tolerance** 0.01 时为 99、101 与分母 100：

```
_resolved_freq * div_freq_tol_lo <= f_hw * div_freq_tol_den
_resolved_freq * div_freq_tol_hi >= f_hw * div_freq_tol_den
```

**N** 与 **ratio**：**N** 为 0 时 **ratio** 为 1；**N** 大于 0 时 **ratio** 为 **N + 1**。反之 **ratio** 不大于 1 时 **N** 为 0，否则 **N** 为 **ratio − 1**。

## div_r

硅片固定分频，无寄存器；**ratio** 由配置指定，只要求大于 0，不受上一节 64 上限。

| 参数 | 说明 |
| --- | --- |
| **f** | 本节点输出频率 |
| **f_ref** | 前级节点频率 |
| **ratio** | 固定分频比，大于 0 |

```
f_hw = f_ref / ratio
```

频率容差与 **div** 相同，由 **period_tolerance** 导出 **div_freq_tol_lo**、**div_freq_tol_hi**。

## cpu_gate

| 参数 | 说明 |
| --- | --- |
| **f** | 本节点输出频率 |
| **f_ref** | 前级节点频率 |
| **ratio** | 分频比，只能取 2、3、4、6 |
| **div** | **div** field 写入值，4 bit |

```
f_hw = f_ref / ratio
```

**\_resolved_freq** 容差同 **div** 节。

**div** 与 **ratio** 按 bit 前缀编码：

| **div** | **ratio** |
| --- | --- |
| 4'b0000、4'b0001 | 2 |
| 4'b001x | 3 |
| 4'b01xx | 4 |
| 4'b1xxx | 6 |

写入时 **ratio** 为 2、3、4、6 分别写 4'h0、4'h2、4'h4、4'h8。

## dto

| 参数 | 说明 |
| --- | --- |
| **f** | 本节点输出频率 |
| **f_ref** | 前级节点频率 |
| **ratio** | 分频比，大于 0 且不超过 2^25 |
| **step** | **step** 寄存器写入值；旁通时为 0，分频时为 1～2^25−1 |
| **bypass** | 旁通开关；**ratio** 为 1 时写 1，否则写 0 |

```
f_hw = f_ref / ratio
```

**\_resolved_freq** 容差同 **div** 节。

```
step = 2^25 / ratio
ratio = 2^25 / step
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
clkf = f / f_ref
```

输出近似 **f_ref × clkf**。

### sc

| 参数 | 说明 |
| --- | --- |
| **f_actual** | 由系数算出的输出频率 |
| **fbdiv** | 反馈分频，1～4095，四舍五入取整 |
| **refdiv** | 参考分频，1～63 |
| **postdiv1** | 后分频 1，1～7 |
| **postdiv2** | 后分频 2，1～7 |
| **fbdiv_min** | 优先选取的 **fbdiv** 下限 |
| **fbdiv_max** | 优先选取的 **fbdiv** 上限 |

```
f_actual = f_ref × fbdiv / refdiv / postdiv1 / postdiv2
```

在合法组合中使 **f_actual** 与 **f** 绝对误差最小；先在 **fbdiv_min**～**fbdiv_max** 内搜，无解再搜全硬件范围。

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

## 测量相位

| 参数 | 说明 |
| --- | --- |
| **t_rise** | 当前上升沿时刻 |
| **t_ref** | 本次 **start_measure** 后第一个上升沿时刻，作为该路 0 时刻 |
| **T** | 当前测得周期 |
| **phase_frac** | 归一化相位，取值 0 以上且小于 1 |

```
phase_frac = fmod(t_rise - t_ref, T) / T
```

**phase_frac** 为 **real**，表示周期内位置；频率达到 **freq_stable** 后读数有效。测量分两阶段：**ACTIVE_CYCLES** 个连续上升沿确认有活动；活动确认后占空比与频率并行采样，各自独立计数 **STABLE_CYCLES** 个连续稳定周期，中途失稳则对应计数清零。活动阶段自 **start_measure** 起超过一个最低频率周期仍无边沿则置 **inactive**，表示频率低于可测下限或无时钟；已见边沿但未采够 **ACTIVE_CYCLES** 且距上一边沿超过该周期同样置 **inactive**。测量结束可通过 **last_freq_hz**、**last_duty**、**last_phase_frac** 读取最近一次结果。

### dw

| 参数 | 说明 |
| --- | --- |
| **f_actual** | 由系数算出的输出频率 |
| **fbdiv** | 反馈分频，1～1023，四舍五入取整 |
| **p** | 后分频索引，0～7 |
| **postdiv** | **p + 1** |

```
f_actual = f_ref × fbdiv / postdiv
```

在 **p** 为 0～7 范围内搜索，使 **f_actual** 与 **f** 绝对误差最小。
