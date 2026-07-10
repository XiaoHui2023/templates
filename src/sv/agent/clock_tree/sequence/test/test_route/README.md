# test_route

沿 **gate**、**mux**、**div**、**dto** 等带寄存器的节点做结构探测：对每个 subject 枚举自身控制量取值组合，再与路径上其它节点的组合做笛卡尔积，每次写寄存器后跑 **check_measure**。

## req

| 成员 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | | 时钟树 |
| **quiet** | **bit** | `0` | 为真时压缩日志 |
| **debug** | **bit** | `0` | 为真时 **check_measure** 打印等待进度 |

## 流程

1. 执行一次 **config_reg**。
2. 收集 stable **clk** 上游路径，路径上的 **gate**、**mux**、**div**、**pll** 固定，不作为 subject。
3. 进入 **optimized_config**，优化 **PLL** 频率，固定非 stable 路径上的 **div** / **dto** 为 1。
4. 对每个 subject 枚举自身取值，再枚举上下游 line 组合。
5. 每轮只测 subject 上下游相通支路，关闭反选支路 **gate**，反选节点写入 **check_measure.skip_nodes**。
6. stable **clk** 失效时跳过该组合。

## rsp

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **ok** | **bit** | 全部未跳过组合通过 |
