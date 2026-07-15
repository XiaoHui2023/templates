# ConnectionCheck

`ConnectionCheck` 用于一次性确认两根信号是否真实连通。宏只能放在 `initial`、`task`、`function` 等过程上下文中使用，`SRC` 必须是可以被 `force` 和 `release` 的左值。

```systemverilog
initial begin
    `ConnectionCheck(src_signal, dst_signal)
    `ConnectionCheckDelay(src_signal, dst_signal, 5ns)
end
```

## 宏入口

| 宏 | 说明 |
| --- | --- |
| `` `ConnectionCheck(SRC, DST)`` | 默认等待 `0ns` 后检查。 |
| `` `ConnectionCheckDelay(SRC, DST, DELAY)`` | `DELAY` 使用 SV 时间表达式，例如 `1ns`、`10ps`。 |

## 检查行为

宏会先比较 `SRC` 与 `DST` 当前值。不一致时触发 `uvm_error`。

随后记录 `SRC` 当前值，执行 `force SRC = ~SRC`，等待指定延迟，再检查 `DST` 是否等于 force 后的值。不一致时触发 `uvm_error`。

检查结束后执行 `release SRC`。
