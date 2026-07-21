# Connectioninterface

`Connectioninterface` 接在源信号和目标信号之间，`check_enable` 为 `1` 后开始监听。输入变化会进入队列，输出变化时按顺序比对，并检查响应延迟是否超过 `LATENCY`。

```systemverilog
Connectioninterface #(
    .DW(8),
    .LATENCY(5.0),
    .CHECK_ENABLE_DEFAULT(1'b0)
) u_conn (
    .in(src_signal),
    .out(dst_signal)
);

initial begin
    u_conn.check_enable = 1'b1;
end
```

## 例化参数

| 参数 | 默认来源 | 说明 |
| --- | --- | --- |
| `DW` | `default_data_width` | 信号位宽。 |
| `LATENCY` | `default_latency` | 允许响应延迟，按该文件 `timeunit` 计。 |
| `CHECK_ENABLE_DEFAULT` | `check_enable_default` | `check_enable` 初始值。 |

## 检查行为

使能时会立即比较一次 `in` 和 `out`。之后 `in` 每次变化都会记录期望值和时间，`out` 变化时取队首期望值比较。

目标信号无源变化、目标值不等于队首输入值、响应延迟超过 `LATENCY`，都会触发 `uvm_error` 并关闭 `check_enable`。
