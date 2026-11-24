# route_check

检查前级输出到后级输入的RTL连线，不验证器件内部功能。各前级串行检查，同一输出连接的输入一起比较。

tree需要build并connect。开始时执行一次低功耗配置，之后不再写寄存器。

## 调用

```systemverilog
clk_tree_route_check_req req;
clk_tree_route_check_seq seq;

req = clk_tree_route_check_req::type_id::create("req");
req.tree = tree;
seq = clk_tree_route_check_seq::type_id::create("route");
seq.req = req;
seq.start(clk_agt.sqr);
```

在已有tree和clk_agt的task中执行。快捷调用为 `clk_agt.sqr.test_route()`。

| req成员 | 默认值 | 说明 |
| --- | --- | --- |
| `tree` | null | 待检查的时钟树 |
| `timeout_ns` | 1000000 | 每个前级的总检查时限，ns |
| `idle_window_ns` | 100 | 等待原生跳变的最短观察窗口，ns |
| `settle_ns` | 0.001 | 跳变后的传播等待，ns |
| `drive_hold_ns` | 1 | 空闲探测的基本保持时间，ns |
| `transitions` | 6 | 原生跳变数或探测电平数 |

`auto` 的观察窗口至少为已知前级输出频率的两个周期，但不超过总时限。按连线传播时间设置 `settle_ns`，它应短于原生时钟的最短高、低电平，也应短于 `drive_hold_ns`。

## 输出活动

在节点上填写 `expected_activity`，以 route 完成低功耗配置后的状态为准：

| 值 | 前级输出 | 检查方式 |
| --- | --- | --- |
| `static` | 确认不会自行跳变 | 不等跳变，直接探测；无驱动权限则立即报错 |
| `auto` | 可能跳变 | 先观察；窗口内无跳变且允许接管时探测 |
| `toggling` | 必须自行跳变 | 只读检查，未出现跳变则超时报错，不接管 |

不填时按插件的输出特性判断。显式填 `auto` 也会覆盖插件判断。

| 节点 | 未指定时 |
| --- | --- |
| `source` | 正频率表示应有自然跳变；其余为 `auto` |
| `source_pad` | `auto`；标称频率不保证外部激励已开启 |
| `pll_sc`、`pll_dw`、`pll_inno`、`pll_tci` | 配置为运行且已读到锁定时为 `toggling`；其余为 `auto`，因为可能旁路 |
| `clk`、`cell`、`inv`、`inv_cell` | 跟随上游；无上游时为 `auto` |
| `gate` | 固定关闭为 `static`；固定开启或已配置为开启时跟随上游；可编程关闭为 `auto`，寄存器写回不代表门控已经切换 |
| `mux`、`inv_mux` | 跟随固定选项或已确认切换完成的输入；输入未知时为 `auto` |
| `div_div`、`div_div_r`、`div_dto` | `auto`；分频目标值不能确认输出已启动或停止 |
| `clk_div_with_clken` | `clk_arm_core` 跟随上游；`hclk` 和 `hclken` 为 `auto` |

新插件可重载 `default_output_activity`，直接返回活动预期，或通过 `upstream` 指定一个可继承预期的输入。

## 逐路检查

1. 按source收集前级输出及全部后级输入，缺接口或关闭检查的连线打印skip。
2. 按前级的有效输出活动预期选择原生观察或空闲探测。
3. 没有活动且端口允许接管时，交替驱动0、1，保持时间依次为基本时间的1、2、3倍，直到完成指定数量。
4. 每个检查点比较前级实际电平及全部后级输入。原生跳变中止、驱动不生效或输入不符均报错。
5. 释放此次建立的驱动，继续下一个前级；原有驱动不释放。

clk和cell可让同一接口充当输入与输出。stable时钟、PLL及外部输入均按相同流程处理。

## 驱动权限

`allow_override` 默认为 1。前级或任一后级正在驱动，或不允许接管时，无法执行空闲探测；`auto` 继续观察至总时限。`static` 不授予覆盖外部驱动的权限。

外部独立使用force时，测试前将对应接口的allow_override设为0：

```systemverilog
clk_tree_if.xtal_out_default.allow_override = 0;
```

普通RTL赋值会被force覆盖，不是额外叠加一个电气驱动；独立force之间没有可移植的自动占用查询。观察窗口内没有跳变也不代表外部没有驱动，权限应由激励拥有者确定。

只读检查证明采样跳变与电平相符，不能区分接到了另一根完全同频同相的信号。需要唯一连线证明时，应由激励拥有者提供有区分度的激励，不能把静止电平相同算作通过。

## 结果

每条连线打印test或skip，test注明原生观察或空闲探测。源端异常和超时影响该前级全部连线；输入比较失败累计后继续检查。

rsp.failed是失败比较次数，源端异常按受影响连线数累计，不是失败器件数。rsp.ok表示已执行检查全部通过；部分skip不代表完整覆盖。

没有source连线、全部连线跳过或前级未返回检查状态时报告fatal。检查时限不包含开始前的寄存器配置；外部终止仿真不保证清理。
