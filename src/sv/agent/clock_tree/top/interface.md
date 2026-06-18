# 接口

![](../images/interface_structure.drawio.svg)

## interface

| 项 | 值 |
| --- | --- |
| **timeunit** | **1ns** |
| **timeprecision** | **1fs** |

### 端口

| 端口 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| **in** | input | wire | RTL 时钟 |

### parameter

| 名字 | 类型 | 说明 |
| --- | --- | --- |
| **MIN_FREQ_HZ** | int | 测量最低频率与无边沿超时，Hz |
| **STABLE_CYCLES** | int | 频率或占空比各自连续稳定所需周期数 |
| **PERIOD_TOL** | real | 相邻周期相对偏差上限 |
| **DUTY_MIN_PCT** | real | 允许占空比下限，百分数 |
| **DUTY_MAX_PCT** | real | 允许占空比上限，百分数 |

### 成员

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **meas** | **measure_interface** | 边沿频率、占空比与相位测量 |

### set_measure_en

写测量开关；关时写入 **last_*** 快照并清零当前测量结果。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| **en** | input | bit | 测量开关 |

### start_measure

清零当前测量结果后开启测量。

### stop_measure

关闭测量并写入 **last_*** 快照。

### set_min_freq_hz

写可测量的最低频率。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| **hz** | input | int | 最低频率，Hz |

### wait_measure_stable

轮询 **freq_stable** 与 **duty_stable**，最长等待 **meas_timeout_ns_rt**；超时置 **timed_out**。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| **need_freq** | input | bit | 为真时等待 **freq_stable** |
| **need_duty** | input | bit | 为真时等待 **duty_stable** |
| **ok** | output | bit | 为真表示在时限内达到所需稳定 |

## measure_interface

| 项 | 值 |
| --- | --- |
| **timeunit** | **1ns** |
| **timeprecision** | **1fs** |

### 端口

| 端口 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| **in** | input | wire | RTL 时钟 |

### parameter

| 名字 | 类型 | 说明 |
| --- | --- | --- |
| **MIN_FREQ_HZ** | int | 测量最低频率与无边沿超时，Hz |
| **STABLE_CYCLES** | int | 频率或占空比各自连续稳定所需周期数 |
| **PERIOD_TOL** | real | 相邻周期相对偏差上限 |
| **DUTY_MIN_PCT** | real | 允许占空比下限，百分数 |
| **DUTY_MAX_PCT** | real | 允许占空比上限，百分数 |

### 成员

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **meas_en** | bit | 测量开关 |
| **active** | logic | 已采到有效边沿 |
| **freq_hz** | real | 当前测得频率，Hz |
| **duty** | real | 当前占空比，0～1 |
| **duty_ok** | logic | 当前占空比在 **DUTY_MIN_PCT**～**DUTY_MAX_PCT** 内 |
| **freq_stable** | logic | 频率已连续 **STABLE_CYCLES** 个周期稳定 |
| **duty_stable** | logic | 占空比已连续 **STABLE_CYCLES** 个周期在允许范围内 |
| **timed_out** | logic | 无边沿或边沿间隔过长导致测量超时 |
| **phase_frac** | real | 当前相位，取值 0 以上且小于 1；频率稳定后有效 |
| **last_freq_hz** | real | 最近一次测量结束时的频率，Hz |
| **last_duty** | real | 最近一次测量结束时的占空比 |
| **last_phase_frac** | real | 最近一次测量结束时的相位 |
| **last_valid** | logic | **last_*** 快照是否有效 |

### set_measure_en

写测量开关；关时写入 **last_*** 快照并清零当前测量结果。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| **en** | input | bit | 测量开关 |

### start_measure

清零当前测量结果后开启测量。

### stop_measure

关闭测量并写入 **last_*** 快照。

### set_min_freq_hz

写可测量的最低频率。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| **hz** | input | int | 最低频率，Hz |

### wait_measure_stable

轮询 **freq_stable** 与 **duty_stable**，最长等待 **meas_timeout_ns_rt**；超时置 **timed_out**。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| **need_freq** | input | bit | 为真时等待 **freq_stable** |
| **need_duty** | input | bit | 为真时等待 **duty_stable** |
| **ok** | output | bit | 为真表示在时限内达到所需稳定 |
