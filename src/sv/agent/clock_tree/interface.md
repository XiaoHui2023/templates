# 接口

## interface

- timeunit：**1ns**
- timeprecision：**1fs**

### 端口

| 端口 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| in | input | wire | RTL 时钟 |

### parameter

| 名字 | 类型 | 说明 |
| --- | --- | --- |
| MIN_FREQ_HZ | int | 测量最低频率与无边沿超时，Hz |
| STABLE_CYCLES | int | 判定 **stable** 的连续稳定周期数 |
| PERIOD_TOL | real | 相邻周期相对偏差上限 |
| DUTY_MIN_PCT | real | 允许占空比下限，百分数 |
| DUTY_MAX_PCT | real | 允许占空比上限，百分数 |

### 内部信号

| 信号 | 类型 | 说明 |
| --- | --- | --- |
| meas | measure_interface | 边沿频率与占空比测量 |

### set_measure_en

写测量开关；关时清零测量结果。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| en | input | bit | 测量开关 |

### start_measure

清零测量结果后开启测量。

### stop_measure

关闭测量并清零测量结果。

### set_min_freq_hz

可测量的最低频率，单位 Hz。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| hz | input | int | 最低频率，Hz |

### wait_measure_stable

轮询 **stable**，最长 **meas_timeout_ns_rt**。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| ok | output | bit | 为真表示在时限内达到稳定 |

## measure_interface

- timeunit：**1ns**
- timeprecision：**1fs**

### 端口

| 端口 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| in | input | wire | RTL 时钟 |

### parameter

| 名字 | 类型 | 说明 |
| --- | --- | --- |
| MIN_FREQ_HZ | int | 测量最低频率与无边沿超时，Hz |
| STABLE_CYCLES | int | 判定 **stable** 的连续稳定周期数 |
| PERIOD_TOL | real | 相邻周期相对偏差上限 |
| DUTY_MIN_PCT | real | 允许占空比下限，百分数 |
| DUTY_MAX_PCT | real | 允许占空比上限，百分数 |

### 内部信号

| 信号 | 类型 | 说明 |
| --- | --- | --- |
| meas_en | bit | 测量开关 |
| active | logic | 已采到有效边沿 |
| freq_hz | real | 测得频率，Hz |
| duty | real | 占空比，0～1 |
| duty_ok | logic | 占空比在 **duty_min**～**duty_max** 内 |
| stable | logic | 周期连续稳定，或无边沿超时结束 |

### set_measure_en

写测量开关；关时清零测量结果。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| en | input | bit | 测量开关 |

### start_measure

清零测量结果后开启测量。

### stop_measure

关闭测量并清零测量结果。

### set_min_freq_hz

可测量的最低频率，单位 Hz。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| hz | input | int | 最低频率，Hz |

### wait_measure_stable

轮询 **stable**，最长 **meas_timeout_ns_rt**。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| ok | output | bit | 为真表示在时限内达到稳定 |
