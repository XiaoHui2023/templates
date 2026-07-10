# test_measure

写寄存器后测试频率与占空比；一次 **check_measure** 并行校验。

## req

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **tree** | **tree_base** | 时钟树 |
| **quiet** | **bit** | 静默打印 |
| **debug** | **bit** | 为真时 **check_measure** 打印等待进度 |
| **check_freq** | **bit** | 为真时检查 **clk** 频率 |
| **check_duty** | **bit** | 为真时检查全部带 **vif** 节点占空比 |

## 流程

1. 执行 **config_reg**。
2. 执行 **check_measure**。
3. 返回两个子步骤的合并结果。

## rsp

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **ok** | **bit** | 子步骤全部通过 |
