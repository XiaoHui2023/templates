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
| **MIN_FREQ_HZ** | int | 测量最低频率与活动、稳定阶段超时时限基准，Hz |
| **ACTIVE_CYCLES** | int | 判定时钟有活动所需连续上升沿个数 |
| **STABLE_CYCLES** | int | 活动确认后频率或占空比各自连续稳定所需周期数 |
| **PERIOD_TOL** | real | 相邻周期相对偏差上限 |
| **DUTY_MIN_PCT** | real | 允许占空比下限，百分数 |
| **DUTY_MAX_PCT** | real | 允许占空比上限，百分数 |
| **DUTY_TOL_PCT** | real | 占空比允许范围在 **DUTY_MIN_PCT**、**DUTY_MAX_PCT** 之外的容差，百分数点 |

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

### measure_freq_hz

一次完成频率测量：调用 **start_measure**、**wait_measure_stable** 仅等待 **freq_stable**，再 **stop_measure**。最低频率与超时由 **MIN_FREQ_HZ** 参数及 agent 已写入的 **set_min_freq_hz** 决定。频率读 **last_freq_hz**，是否有效读 **last_valid**；失败时 **inactive** 或 **timed_out** 为 1。

### wait_measure_stable

先轮询 **activity_ok** 或 **inactive**，最长 **active_timeout_ns_rt**；活动阶段自测量起点或上一边沿起超过一个最低频率周期仍无边沿则 **inactive** 为 1。活动已确认后再轮询 **freq_stable** 与 **duty_stable**，最长 **stable_timeout_ns_rt**。活动已确认但稳定阶段超时则置 **timed_out**。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| **need_freq** | input | bit | 为真时等待 **freq_stable** |
| **need_duty** | input | bit | 为真时等待 **duty_stable** |
| **ok** | output | bit | 为真表示活动已确认且在稳定时限内达到所需稳定 |

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
| **MIN_FREQ_HZ** | int | 测量最低频率与活动、稳定阶段超时时限基准，Hz |
| **ACTIVE_CYCLES** | int | 判定时钟有活动所需连续上升沿个数 |
| **STABLE_CYCLES** | int | 活动确认后频率或占空比各自连续稳定所需周期数 |
| **PERIOD_TOL** | real | 相邻周期相对偏差上限 |
| **DUTY_MIN_PCT** | real | 允许占空比下限，百分数 |
| **DUTY_MAX_PCT** | real | 允许占空比上限，百分数 |
| **DUTY_TOL_PCT** | real | 占空比允许范围在 **DUTY_MIN_PCT**、**DUTY_MAX_PCT** 之外的容差，百分数点 |

### 成员

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **meas_en** | bit | 测量开关 |
| **active** | logic | 与 **activity_ok** 同义，已连续 **ACTIVE_CYCLES** 个上升沿 |
| **activity_ok** | logic | 活动阶段通过 |
| **inactive** | logic | 活动阶段结束：自测量起点或上一边沿起超过一个最低频率周期仍无边沿，或已见边沿但未采够 **ACTIVE_CYCLES** 个上升沿 |
| **freq_hz** | real | 当前测得频率，Hz |
| **duty** | real | 当前占空比，0～1 |
| **duty_ok** | logic | 当前占空比在 **[DUTY_MIN_PCT − DUTY_TOL_PCT, DUTY_MAX_PCT + DUTY_TOL_PCT]** 内 |
| **freq_stable** | logic | 活动确认后频率已连续 **STABLE_CYCLES** 个周期稳定 |
| **duty_stable** | logic | 活动确认后占空比已连续 **STABLE_CYCLES** 个周期在允许范围内 |
| **timed_out** | logic | 活动已确认但在稳定阶段时限内未达到 **STABLE_CYCLES** 稳定 |
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

### measure_freq_hz

一次完成频率测量：调用 **start_measure**、**wait_measure_stable** 仅等待 **freq_stable**，再 **stop_measure**。最低频率与超时由 **MIN_FREQ_HZ** 参数及 agent 已写入的 **set_min_freq_hz** 决定。频率读 **last_freq_hz**，是否有效读 **last_valid**；失败时 **inactive** 或 **timed_out** 为 1。

### wait_measure_stable

先轮询 **activity_ok** 或 **inactive**，最长 **active_timeout_ns_rt**；活动阶段自测量起点或上一边沿起超过一个最低频率周期仍无边沿则 **inactive** 为 1。活动已确认后再轮询 **freq_stable** 与 **duty_stable**，最长 **stable_timeout_ns_rt**。活动已确认但稳定阶段超时则置 **timed_out**。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| **need_freq** | input | bit | 为真时等待 **freq_stable** |
| **need_duty** | input | bit | 为真时等待 **duty_stable** |
| **ok** | output | bit | 为真表示活动已确认且在稳定时限内达到所需稳定 |
