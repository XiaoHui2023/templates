# 频率与编码

频率单位均为Hz。f_in是前级频率，f_out是寄存器编码对应的实际输出频率，不是约束容差范围内的随机结果。

## 整数分频

```text
code = ratio - 1
f_out = f_in / ratio
```

可编程div_div支持1至30位控制字段；宽度w可编码1至2^w分频，实际目标还受max_ratio限制。固定分频不受该max_ratio上界约束。div_div_r没有寄存器，直接使用固定ratio。

分频约束先取整数商，再给频率一个小范围：

```text
f_hw = floor(f_in / ratio)
floor(f_hw × (1 - epsilon)) <= resolved_freq
resolved_freq <= floor(f_hw × (1 + epsilon))
```

epsilon使用divider.freq_tolerance，默认0.01。它不改变寄存器编码、不改变实际输出，也不代替测量允许误差。

## CPU三输出分频

clk_div_with_clken使用四位控制字段：

| 编码 | ratio |
| --- | --- |
| 000x | 2 |
| 001x | 3 |
| 01xx | 4 |
| 1xxx | 6 |

```text
f_clk_arm_core = f_in
f_hclk = f_in / ratio
f_hclken = f_hclk
```

## DTO

```text
M = 2^25
step = floor(M / ratio)
f_out = f_in × min(step, M - step) / M
```

折叠公式只用于非旁通输出。ratio为1时写bypass=1、step=0、load=1，输出直接等于输入。

非旁通step=0没有时钟，step=M/2输出输入频率的一半，超过M/2后折叠。step有效范围固定为25位；寄存器更宽不扩大算法范围，更窄则要求编码能完整写入，不能截断。

## PLL

### SC

```text
f_pfd = f_in / refdiv
f_vco = f_pfd × fbdiv
f_out = f_vco / postdiv1 / postdiv2
```

refdiv为1至63，postdiv1和postdiv2为1至7。fbdiv、PFD和VCO边界由SC插件设置。

搜索先排除违反PFD、VCO和字段范围的组合，再检查合法区间内最接近理想值的两个fbdiv。比较精确输出误差；同误差优先高PFD，再优先高VCO。没有合法解或最佳解超出允许误差时，在写寄存器前报错。

重复配置按读回编码反算实际频率并比较容差，不要求与重新搜索出的系数逐位一致。不同合法编码可以提供相同频率；电源、旁通等状态仍要匹配。

### INNO

```text
f_out = f_in × fbdiv / refdiv / postdiv1 / postdiv2
postdiv1 = postdiv1_reg + 1
postdiv2 = postdiv2_reg + 1
```

refdiv为1至63，postdiv为1至7，写入值为0至6。fbdiv受绑定位宽限制，跳过0至7及11。

共享输出先确定fbdiv和refdiv，各路再选择自己的后分频。两组共用系数，不是两颗独立PLL。

### DW

```text
postdiv = p + 1
f_out = f_in × fbdiv / postdiv
```

p为0至7，fbdiv为1至1023。每个后分频尝试最接近目标的反馈系数，取绝对误差最小者。

### TCI

```text
clkr = 1
clkod = 1
clkf = floor(f_target / f_in)
bwadj = clkf
f_out ≈ f_in × clkf
```

## 测量相位

```text
phase_frac = fmod(t_rise - t_first_rise, period) / period
```

这是同一路时钟相对本次首个上升沿的周期内位置，范围为0至1、不含1；不是两路时钟的相位差。
