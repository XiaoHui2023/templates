# 接口

`tree_interface` 包含节点端口的接口实例，`connect(interface, tree)` 将句柄分配给节点。`interface` 负责驱动和转交测量请求，内部的 `meas` 为 `measure_interface`。两者均使用 `timeunit 1ns`、`timeprecision 1fs`。

## 端口与路径

`interface` 和 `measure_interface` 都以 `input wire in` 读取 RTL 信号。`interface` 没有输出端口，驱动通过 `drive_en`、`drive_value` 交给 `tree_interface` 中的 force/release 逻辑。

`path_macros.sv` 为 RTL 路径提供带 `ifndef` 的默认宏定义，可在编译前定义同名宏来替换路径。

## 参数

两个接口使用相同参数；外层将参数传入 `meas`。

| 参数 | 类型 | 含义 |
| --- | --- | --- |
| `MIN_FREQ_HZ` | `int` | 活动和稳定超时的最低频率基准，Hz |
| `ACTIVE_CYCLES` | `int` | 确认活动所需的上升沿数 |
| `STABLE_CYCLES` | `int` | 连续稳定周期数 |
| `PERIOD_TOL` | `real` | 相邻周期的相对偏差上限 |
| `DUTY_MIN_PCT`、`DUTY_MAX_PCT` | `real` | 占空比范围，百分数 |
| `DUTY_TOL_PCT` | `real` | 占空比边界容差，百分数点 |

## 驱动

| task | 作用 |
| --- | --- |
| `drive_static(value)` | 停止时钟激励，持续驱动 0 或 1 |
| `start_clock(freq_hz)` | 产生指定频率的时钟，单位 Hz；非正值不改变驱动 |
| `release_drive()` | 关闭驱动并释放 RTL 信号 |
| `stop_clock()` | 与 release_drive 相同 |

驱动持续到显式释放。所有正常退出和可继续错误路径都要释放驱动。

## 测量

以下方法由 `interface` 转交给 `meas`，也可直接通过 `measure_interface` 调用。

| 方法 | 作用 |
| --- | --- |
| `set_min_freq_hz(hz)` | 设置超时基准，不低于 MIN_FREQ_HZ |
| `start_measure(need_freq=1, need_duty=1)` | 清零当前结果，启动本次测量 |
| `wait_measure_stable(need_freq, need_duty, ok)` | 先等待活动确认，再等待指定项稳定；关闭测量或超时也会返回 |
| `stop_measure()` | 保存有效活动读数，关闭并清零当前结果 |
| `set_measure_en(en)` | 控制测量开关；关闭时保存读数并清零 |
| `measure_freq_hz()` | 启动、等待频率稳定、停止；不等待占空比 |

仅检查活动时，将两个 need 参数均置 0。开始和等待阶段应使用相同的选择。

## 测量结果

以下成员位于 `meas`。

| 成员 | 含义 |
| --- | --- |
| `meas_en` | 测量已开启 |
| `active`、`activity_ok` | 已采够活动上升沿 |
| `inactive` | 活动阶段未通过 |
| `freq_hz` | 当前频率，Hz |
| `duty` | 当前占空比，0～1 |
| `duty_ok` | 占空比在允许范围内 |
| `freq_stable`、`duty_stable` | 对应项目达到连续稳定要求 |
| `timed_out` | 活动已确认，但指定项未及时稳定 |
| `phase_frac` | 相对本次首个上升沿的周期内位置，0～1，不含 1 |
| `last_freq_hz`、`last_duty`、`last_phase_frac` | 最近保存的活动读数 |
| `last_valid` | 曾保存有效活动读数，不表示频率或占空比已稳定 |

停止测量会清零当前状态；停止前读取 `ok` 和错误状态，停止后读取 `last_*`。未确认活动时不会覆盖旧快照，因此不能单凭 `last_valid` 判断本次成功。

## 超时与稳定

1. 活动阶段在最低频率对应的 ACTIVE_CYCLES 个周期内采够上升沿。
2. 活动确认后，频率和占空比分别累计连续稳定周期；失稳时各自重新计数。
3. 稳定预算为 STABLE_CYCLES + 1 个最低频率周期，额外一个周期用于建立频率基准。

最低频率只决定超时，不丢弃已采到的正周期。截止时间包含仿真精度余量，并在截止时间槽结束后判断，避免与最后一个边沿竞争。
