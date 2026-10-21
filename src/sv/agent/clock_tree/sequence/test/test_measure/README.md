# test_measure

编排完整配置和测量检查。tree 必须已经 build，并至少存在一个可观测节点。

## req

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **tree** | **tree_base** | 时钟树 |
| **quiet** | **bit** | 静默打印 |
| **debug** | **bit** | 打印测量进度 |
| **check_observation** | **bit** | 检查所有可观测节点 |
| **check_freq** | **bit** | 检查频率；关闭后仍检查活动 |
| **check_duty** | **bit** | 检查占空比；关闭后仍检查活动 |

## 流程

1. 校验请求、tree 和检查开关。
2. 调用 **tree.configure**，应用本轮随机化配置。
3. 配置成功后启动 **check_measure**，转交全部检查开关。
4. 两个 operation 均成功后返回通过。

## 设计

test 只负责编排，不直接访问寄存器或 interface。配置失败或测量 operation 失败都会立即终止 test，避免在配置未知时继续测量。

## rsp

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **ok** | **bit** | 配置和测量均通过 |
