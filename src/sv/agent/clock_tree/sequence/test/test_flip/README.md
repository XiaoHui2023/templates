# test_flip

测试 **div**、**dto** 控制位翻转

## req

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **tree** | **tree_base** | 时钟树 |
| **quiet** | **bit** | 静默打印 |
| **debug** | **bit** | 为真时 **check_measure** 打印等待进度 |

## 流程

1. 先执行一次 **config_reg**。
2. 收集 stable **clk** 的完整上游 **source** 链，并固定链上的控制节点。
3. 进入 **optimized_config**，优化 **PLL** 频率并放开非 stable **clk** 频率。
4. 对每个 **div** / **dto** 写入翻转 pattern。
5. 只测被测节点上下游相通支路，关闭反选支路 **gate**，无关 **clk** / **cell** 临时约束为 inactive。
6. 恢复配置后测试 **inv** 翻转相位。

## 细节

每个 **div** / **dto** 单独计算相关支路。反选支路上的 **gate** 会关闭，无关 **clk** / **cell** 不参与本轮测量，也不会反向撑开上游路径。

stable **clk** 上游可能经过 **cell** / **inv**。这些节点会随 stable 上游链保留，避免 stable **clk** 仍要求 active 时，上游 **cell** 被反选支路处理临时关掉。

### div / dto

| pattern | 写入意图 |
| --- | --- |
| **MSB**=1、**LSB**=0 | 仅最高位为 1 |
| **MSB**=0、**LSB**=1 | 仅最低位为 1 |

仅 **LSB**=1 不合法时，再将某一个无关辅助位置 1，使配置值合法。

## rsp

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **ok** | **bit** | 全部探测对象通过 |
