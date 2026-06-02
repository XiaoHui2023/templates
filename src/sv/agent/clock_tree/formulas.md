# 频率关系

**div**、**dto**、**pll** 三类节点的频率计算与寄存器换算。符号：**f** 为本节点 **frequence**，**f_ref** 为参考前级 **source.frequence**，单位均为 Hz。

## div

**ratio** 取值 1～64。有前级时

```
f = f_ref / ratio
```

整数除法，与 SystemVerilog 约束一致。

**config_reg** 写 **div** 寄存器：**N** 为 0 表示 **ratio** 为 1；**N** 大于 0 时 **ratio** 为 **N + 1**。换算函数 **div_ratio_to_n**：**ratio** 不大于 1 时 **N** 为 0，否则 **N** 为 **ratio − 1**。

## dto

**ratio** 须大于 0 且不超过 2^25；**ratio** 为 1 时无法写出合法 **step**，随机与写寄存器均应避免。

有前级时

```
f = f_ref / ratio
```

**step** 与 **ratio** 满足

```
step = 2^25 / ratio
ratio = 2^25 / step
```

**step** 须为 1～2^25−1 的整数。**config_reg** 写 **step** 时用 **dto_ratio_to_step** 按上式由 **ratio** 算出 **step**。

## pll

输出 **f** 由 YAML **freq** 软约束或随机。**config_reg** 以参考节点 **f_ref** 与目标 **f** 反算各型号分频系数。

### tci

**clkr**、**clkod** 固定为 1。**clkf** 为整数除法

```
clkf = f / f_ref
```

理想输出近似 **f_ref × clkf**，与目标 **f** 可能因整除有偏差。**bwadj** 与 **clkf** 相同。

### sc

在 **refdiv** 为 1～63、**postdiv1** 与 **postdiv2** 为 1～7、寄存器 **fbdiv** 为 1～4095 的硬件范围内搜索。先在 **settings** 的 **pll_sc_fbdiv_min** 与 **pll_sc_fbdiv_max** 内找绝对误差最小的组合；若无解再放宽到全硬件范围，最终 **fbdiv** 仍超出优先区间时 **uvm_error**。公式

```
f_actual = f_ref × fbdiv / refdiv / postdiv1 / postdiv2
```

与目标 **f** 的绝对误差最小；**fbdiv** 四舍五入取整。

### dw

在 **p** 为 0～7 范围内搜索，分母为 **p + 1**，使

```
f_actual = f_ref × fbdiv / postdiv
```

其中 **postdiv** 为 **p + 1**。与目标 **f** 的绝对误差最小；**fbdiv** 四舍五入取整，范围为 1～1023。
