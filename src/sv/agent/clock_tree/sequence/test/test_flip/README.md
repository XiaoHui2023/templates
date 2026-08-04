# test_flip

启动一次器件寄存器功能检查并返回汇总结果。

## req

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **tree** | **tree_base** | 时钟树 |
| **quiet** | **bit** | 静默打印 |
| **debug** | **bit** | 打印开始信息 |

## 流程

1. 校验请求。
2. 创建 **flip_check** 请求并转交 tree、打印开关。
3. 启动 **flip_check**。
4. 将 operation 的通过状态和失败数写入 test response。

## 设计

test 不直接访问寄存器或 interface，候选筛选、激励、测量、并发控制和清理都由 operation 负责。operation 没有返回 response 时按一次失败处理。

## rsp

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **ok** | **bit** | 器件功能检查通过 |
| **failed** | **int** | 失败检查数 |
