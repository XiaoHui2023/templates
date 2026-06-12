# check_freq

检查频率

## req

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **tree** | **tree_base** | 时钟树 |
| **quiet** | **bit** | 静默打印 |
| **min_freq_hz** | **int** | 允许最低时钟频率 |

## 流程

![check_freq 流程](../../../images/check_freq_flow.drawio.svg)

## rsp

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **ok** | **bit** | 全部节点通过 |
