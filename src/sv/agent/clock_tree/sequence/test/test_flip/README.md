# test_flip

测试 **div**、**dto** 控制位翻转

## req

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **tree** | **tree_base** | 时钟树 |
| **quiet** | **bit** | 静默打印 |

## 流程

![test_flip 流程](../../../images/test_flip_flow.drawio.svg)

## 细节

固定 **gate** / **mux**，探测只改 **div** / **dto** 分频比，不改路由。

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
