# test_flip

测试 **div**、**dto** 控制位翻转。

## req

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **tree** | **tree_base** | 时钟树 |
| **quiet** | **bit** | 静默打印 |
| **debug** | **bit** | 为真时 **check_measure** 打印等待进度 |

## 流程

1. 执行一次 **config_reg**。
2. 收集 stable **clk** 的 **active domain**，并固定其中的控制节点。
3. 进入 **optimized_config**，优化 **PLL** 频率并放开非 stable **clk** 频率。
4. 对每个 **div** / **dto** 写入翻转 pattern。
5. 每轮只把无关 **clk** / **cell** 写入 **check_measure.skip_nodes**。
6. 不关闭无关 **gate**，不把无关 **clk** / **cell** 临时约束为 inactive。
7. 恢复配置后测试 **inv** 翻转相位。

## div / dto

| pattern | 写入意图 |
| --- | --- |
| **MSB**=1、**LSB**=0 | 仅最高位为 1 |
| **MSB**=0、**LSB**=1 | 仅最低位为 1 |

仅 **LSB**=1 不合法时，再将某一个辅助位置 1，使配置值合法。

## rsp

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **ok** | **bit** | 全部探测对象通过 |
