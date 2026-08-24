# probe

`probe` 是一个纯 SystemVerilog 仿真小工具，用于检查一组 RTL 信号的频率状态。

当前只支持两类检查：

- `freq > 0`：测量信号频率，并与期望 Hz 值比较。
- `freq == 0`：在观察窗口内检查信号没有时钟活动。

`freq` 可以省略，省略时等价于 `freq: 0`。YAML 中每个信号只支持 `path` 和 `freq` 字段。写入 `source`、`reg`、`kind`、`active` 等未支持字段会在模型校验阶段报错。

## 输入

```yaml
signals:
  cpu_clk:
    path: dut.u_top.cpu_clk
    freq: 100000000

  sleep_clk:
    path: dut.u_top.sleep_clk

settings:
  prefix: probe_
  tolerance_ppm: 20000
  min_freq_hz: 15000
  stable_cycles: 5
```

## 生成文件

```text
probe/
  README.md
  probe.f.j2
  example.yaml
  models.py
  path_macros.sv.j2
  probe_signal_if.sv.j2
  probe_if.sv.j2
  probe_check.sv.j2
```

渲染后得到的 filelist 内容为：

```text
path_macros.sv
probe_signal_if.sv
probe_if.sv
probe_check.sv
```

仿真工程使用生成后的 filelist：

```text
-F probe/probe.f
```

用户顶层：

```systemverilog
probe_if probe();
bit probe_pass;

initial begin
    probe_check(probe, probe_pass);
    if (!probe_pass)
        $display("probe result is available to caller: failed");
end
```

`probe_check` 的 `pass` 是输出参数。全部信号通过时返回 `1`，任意信号失败时返回 `0`；内部仍会打印逐信号结果，并在总结果失败时调用 `$error`。

所有信号检查并发启动，各信号结果写入独立槽位，全部结束后再统一汇总。总仿真等待时间由最慢信号决定，不随信号数量线性累加。

频率检查的超时上限由 `MIN_FREQ_HZ` 和 `STABLE_CYCLES` 推导，覆盖首个有效上升沿和连续测量周期。inactive 检查只观察一个最低频率周期。总入口另有同样由这两个参数推导的总超时保护；任一子检查未按时返回时，`pass` 保持为 `0` 并报告 `probe: timeout`。超时竞争在独立进程内清理，不会终止调用者已经启动的其它后台进程，也不需要额外配置超时参数。

有效边沿只认定已知电平之间的 `0→1` 或 `0↔1` 变化，X/Z 初始化跳变不计入时钟活动。

生成的总 interface 只给每个子 interface 传该信号自己的频率：

```systemverilog
probe_signal_if #(.FREQ(100000000)) cpu_clk (.sig(`PROBE_PATH_CPU_CLK));
```

`TOLERANCE_PPM`、`MIN_FREQ_HZ`、`STABLE_CYCLES` 是 `probe_signal_if` 内部统一默认参数，由 YAML 的 `settings` 渲染到子 interface 定义里，不在每个实例重复传入。

`settings.prefix` 同时作用于路径宏和全局 SystemVerilog 符号。默认 `probe_` 会生成：

```text
PROBE_PATH_CPU_CLK
PROBE_DISABLE_CPU_CLK
probe_signal_if
probe_if
probe_check
```

如果改成 `pll0_`，会生成：

```text
PLL0_PATH_CPU_CLK
PLL0_DISABLE_CPU_CLK
pll0_signal_if
pll0_if
pll0_check
```

同一仿真里需要编译多份 probe 时，为每份配置不同 `prefix`，避免全局 interface 和 task 重名。

## 路径覆盖

生成的路径宏格式如下：

```systemverilog
`PROBE_PATH_CPU_CLK
```

用户可以在编译 `path_macros.sv` 前提前定义同名宏，覆盖默认 RTL 路径：

```systemverilog
`define PROBE_PATH_CPU_CLK tb.dut_alt.cpu_clk
```

## 节点禁用

为节点定义 `<PREFIX_UPPER>DISABLE_<SIGNAL_NAME>` 宏，可移除该节点的 RTL 路径引用、interface 实例和检查分支：

```text
+define+PROBE_DISABLE_CPU_CLK
```

也可以在编译 `path_macros.sv` 前定义：

```systemverilog
`define PROBE_DISABLE_CPU_CLK
```

禁用节点不参与汇总。全部节点均被禁用时，`probe_check` 返回通过。
