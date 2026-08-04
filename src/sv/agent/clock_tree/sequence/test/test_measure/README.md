# test_measure

编排完整配置和测量检查。tree 必须已经 build，并至少启用一种有效的 **clk/cell** 检查组合。

## req

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **tree** | **tree_base** | 时钟树 |
| **quiet** | **bit** | 静默打印 |
| **debug** | **bit** | 打印测量进度 |
| **check_clk** | **bit** | 检查 **clk** |
| **check_cell** | **bit** | 检查 **cell** |
| **check_freq** | **bit** | 检查频率 |
| **check_duty** | **bit** | 检查占空比 |

## 流程

1. 校验请求、tree 和检查开关。
2. 启动 **config_reg**，应用本轮随机化配置。
3. 配置成功后启动 **check_measure**，转交全部检查开关。
4. 两个 operation 均成功后返回通过。

## 设计

test 只负责顺序编排，不直接访问寄存器或 interface。任一子 operation 无 response 或失败都会立即终止 test，避免在配置未知时继续测量。

## rsp

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **ok** | **bit** | 配置和测量均通过 |
