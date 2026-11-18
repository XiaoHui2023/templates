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
| `STABLE_CYCLES` | `int` | 连续稳定频率样本数；占空比按周期计数 |
| `PERIOD_TOL` | `real` | 相邻平均周期的相对偏差上限 |
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

时钟半周期等待结束后重新检查驱动状态。等待期间切为静态驱动或释放时，旧时钟分支不再翻转驱动值。

## 测量

以下方法由 `interface` 转交给 `meas`，也可直接通过 `measure_interface` 调用。

| 方法 | 作用 |
| --- | --- |
| `set_min_freq_hz(hz)` | 设置超时基准，不低于 MIN_FREQ_HZ |
| `configure_measurement(min_hz, window_cycles=1, max_rise_gap_ns=0)` | 同时设置最低频率、平均周期数及最大上升沿间隔，间隔单位 ns；0 表示按最低频率推算 |
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
| `last_valid` | 本次保存了有效活动读数，不表示频率或占空比已稳定 |

`start_measure` 会清除 `last_valid`。停止测量会清零当前状态；停止前读取 `ok` 和错误状态，停止后读取 `last_*`。活动已确认不等于频率或占空比合格，不能单凭 `last_valid` 判断本次成功。

## 超时与稳定

1. 活动预算为 `ACTIVE_CYCLES × 最大上升沿间隔`；未指定间隔时使用最低频率对应的周期。
2. 频率按多个完整周期的总时间计算。一个平均窗口建立基准，随后累计 `STABLE_CYCLES` 次稳定比较；占空比仍按每个周期检查。
3. 稳定预算为 `(STABLE_CYCLES + 1) × window_cycles × 最大上升沿间隔`。`meas.measurement_timeout_ticks()` 返回包含活动、所需稳定阶段和截止保护的总预算，单位为 fs。

最低频率只决定超时，不丢弃已采到的正周期。截止时间包含仿真精度余量，并在截止时间槽结束后判断，避免与最后一个边沿竞争。

采样使用 `time_domain` 的整数 fs 时间戳，先求时间跨度，再转换为实数计算频率，避免长时间仿真时绝对实数时间相减丢失精度。局部时间声明不改变其他模块的默认单位，但不能恢复信号产生时已被舍入的边沿。
