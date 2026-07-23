# check_measure

同时检查频率与占空比；interface 一次 **start_measure** 并行观测。活动阶段超过一个最低频率周期仍无边沿则 **inactive**；采够 **active_cycles** 个上升沿后进入稳定计数 **stable_cycles**。

## req

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **tree** | **tree_base** | 时钟树 |
| **quiet** | **bit** | 静默打印 |
| **debug** | **bit** | 为真时等待循环打印未完成节点与测量阶段 |
| **check_clk** | **bit** | 为真时检查 **clk** |
| **check_cell** | **bit** | 为真时检查 **cell** |
| **check_freq** | **bit** | 为真时检查 **clk/cell** 频率 |
| **check_duty** | **bit** | 为真时检查带 **vif** 且节点 **check_duty** 为真的 **clk** 占空比；**cell** 不检查占空比 |
| **min_freq_hz** | **int** | 允许最低时钟频率；0 则用 **settings.min_freq_hz** |
| **skip_nodes** | **node_base** 队列 | 不参与本次测量的节点 |

## 流程

1. 收集带 **vif**、未在 **skip_nodes** 中的本轮量测节点。
2. 同一个 **vif** 只启动一次测量。
3. 等待活动确认、频率稳定和占空比稳定。
4. 按 **clk/cell** 的 **_resolved_freq** 比对频率。
5. 全部本轮量测节点完成后关闭空闲 **vif**。

## rsp

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **ok** | **bit** | 全部节点通过 |
| **failed_nodes** | **node_base** 队列 | 占空比未通过节点 |
