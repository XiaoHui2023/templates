# test_route

检查器件之间的 RTL 连线。

## 输入

| 节点 | 端口 |
| --- | --- |
| 单输出前级 | **out_path** |
| mux 输入 | **in_paths** |
| 单输入后级 | **in_path** |
| clk / cell | **path** |

缺少任一端口时跳过该连线并打印原因。

## 流程

1. 执行 **low_power** 并写入配置。
2. 按 **source** / **mux.source** 收集连线。
3. force 前级 **out** 为 0，检查后级 **in** 为 0。
4. force 前级 **out** 为 1，检查后级 **in** 为 1。
5. release 前级 **out**。

PLL 只参与连线检查。
