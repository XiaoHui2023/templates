# 节点 interface

展开类型名带 **class_prefix** 前缀；下文标题与表仅用后缀名。

## interface

timeunit **1ns**、timeprecision **1fs**。

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| in | input wire | RTL 时钟 |
| meas | measure_interface | |

**function** / **task** 与 **meas** 同名成员一一转发。

## measure_interface

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| in | input wire | RTL 时钟 |
| meas_en | bit | 量测开关 |
| active | logic | 已采到有效边沿 |
| freq_hz | real | 频率，Hz |
| duty | real | 占空比，0～1 |
| duty_ok | logic | 在 **duty_min**～**duty_max** 内 |
| stable | logic | 周期稳定或无边沿超时 |
| set_measure_en | function | 写 **meas_en**；关时清零 |
| start_measure | function | 清零后开 **meas_en** |
| stop_measure | function | 关 **meas_en** 并清零 |
| set_min_freq_hz | function | 最低可量测频率，Hz |
| wait_measure_stable | task | 轮询 **stable**；**ok** 为时限内是否稳定 |
