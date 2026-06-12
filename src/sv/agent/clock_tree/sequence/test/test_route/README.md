# test_route

测试路由结构

## req

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **tree** | **tree_base** | 时钟树 |
| **always_active_clk_nodes** | **node_base** 队列 | 每轮都要活动的 **clk**；空队列表示全部 **clk** |
| **quiet** | **bit** | 静默打印 |

## 流程

![test_route 流程](../../../images/test_route.drawio.svg)

## rsp

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **ok** | **bit** | 全部未跳过组合通过 |
