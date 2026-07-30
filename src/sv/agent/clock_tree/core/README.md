# core

## optimized_config

test_route 和 test_flip 进入寄存器探测前使用同一组优化配置。

1. 取最小正 **source** 频率作为晶振频率。
2. 按小于 1GHz 的最大晶振倍数配置第一个 **PLL**，其它 **PLL** 倍数依次减 1。
3. stable **active domain** 内的 **PLL**、**div**、**dto** 保持原配置。
4. 非 stable **clk** 放开频率约束；有 stable **clk** 时也放开非 stable **clk** 的使能约束。
