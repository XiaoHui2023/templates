# test_measure

写寄存器后测试频率与占空比；一次 **check_measure** 并行校验。

## req

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **tree** | **tree_base** | 时钟树 |
| **quiet** | **bit** | 静默打印 |
| **debug** | **bit** | 为真时 **check_measure** 打印等待进度 |
| **check_freq** | **bit** | 为真时检查 **source**、**clk**、**pll** 频率 |
| **check_duty** | **bit** | 为真时检查全部带 **vif** 节点占空比 |

## 流程

![test_measure 流程](../../../images/test_measure_flow.drawio.svg)

## rsp

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **ok** | **bit** | 子步骤全部通过 |
