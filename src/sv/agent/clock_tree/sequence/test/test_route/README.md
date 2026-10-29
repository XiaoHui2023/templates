# test_route

启动一次 RTL 连线检查并返回汇总结果。

## req

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **tree** | **tree_base** | 时钟树 |

## 流程

1. 校验请求。
2. 创建 **route_check** 请求并转交 tree、打印开关。
3. 启动 **route_check**。
4. 将 operation 的通过状态和失败数写入 test response。

## 设计

test 不直接驱动 interface 或写寄存器。operation 没有返回 response 时按一次失败处理，其余结果原样转交。

## rsp

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **ok** | **bit** | 连线检查通过 |
| **failed** | **int** | 失败比较次数 |
