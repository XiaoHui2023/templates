# 节点 interface

展开类型名带 **class_prefix** 前缀；下文标题与表仅用后缀名。

## interface

配置中为该节点填写 RTL 路径时，**tree_connection** 例化 **interface** 并将 **in** 接到该路径；时间单位为 **1ns**、精度 **1fs**。接线步骤见 **README** **顶层连线**。

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| in | input wire | 被测输入 |
| meas | measure_interface | 边沿测量 |
| set_measure_en | function | 设置 **meas.meas_en** |
| start_measure | function | 清零并开启 **meas_en** |
| stop_measure | function | 关闭测量并清零结果 |
| wait_measure_stable | task | 轮询 **stable**，超时返回 **ok** 为假 |

## measure_interface

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| in | input wire | 被测时钟 |
| meas_en | bit | 测量开关 |
| active | logic | 已采到有效边沿 |
| freq_hz | real | 测得频率，单位 Hz；边沿间隔按 **timeunit 1ns** 与 **$realtime** 一致 |
| duty | real | 占空比，0～1 小数；日志按百分数展示 |
| duty_ok | logic | 占空比在 **duty_min**～**duty_max** 闭区间内 |
| stable | logic | 连续稳定 |
| set_measure_en | function | 写 **meas_en**；关时清零测量结果 |
| start_measure | function | 清零后开启 **meas_en** |
| stop_measure | function | 关闭 **meas_en** 并清零 |
| wait_measure_stable | task | 在 **MEAS_TIMEOUT_NS** 内轮询 **stable**；**ok** 表示是否在时限内稳定 |
