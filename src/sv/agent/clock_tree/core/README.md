# core

## optimized_config

test_route 和 test_flip 进入寄存器探测前使用同一组优化配置。

1. 取最小正 **source** 频率作为晶振频率。
2. 按小于 1GHz 的最大晶振倍数配置第一个 **PLL**，其它 **PLL** 倍数依次减 1。
3. stable **active domain** 内的 **PLL**、**div**、**dto** 保持原配置。
4. 非 stable **clk** 放开频率约束；有 stable **clk** 时也放开非 stable **clk** 的使能约束。
5. 每次探测一个寄存器时，只把无关 **clk** / **cell** 写入 **check_measure.skip_nodes**。
6. 不关闭无关 **gate**，不把无关 **clk** / **cell** 临时约束为 inactive。
