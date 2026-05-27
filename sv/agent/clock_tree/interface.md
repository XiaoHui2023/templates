# 节点 interface

展开类型名带 **class_prefix** 前缀；下文标题与表仅用后缀名。

## interface

每节点在 **path** 非空时例化一个 **interface** 实例；时间单位为 **1ns**、精度 **1fs**。

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| in | input wire | 观测输入 |
| out | output wire | 驱动输出 |
| gen | generate_interface | 时钟发生 |
| meas | measure_interface | 边沿测量 |
| set_clock_gen | function | 设置 **gen.gen_en** 与 **gen.gen_hz** |
| set_measure_en | function | 设置 **meas.meas_en** |

## generate_interface

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| out | output wire | **gen_en** 为真时等于 **gen_clk**，否则高阻 |
| gen_en | bit | 发生开关 |
| gen_hz | real | 发生频率，单位 Hz |
| gen_clk | reg | 内部方波 |
| set_clock_gen | function | 写 **gen_en**、**gen_hz** |

## measure_interface

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| in | input wire | 被测时钟 |
| meas_en | bit | 测量开关 |
| active | logic | 已采到有效边沿 |
| freq_hz | real | 测得频率，单位 Hz |
| duty | real | 占空比 |
| duty_ok | logic | 占空比在容差内 |
| stable | logic | 连续稳定 |
| set_measure_en | function | 写 **meas_en**；关时清零测量结果 |
