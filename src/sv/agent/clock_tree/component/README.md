# UVM 组件

![](../images/component_structure.drawio.svg)

## config_db

| 键 | 类型 | 说明 |
| --- | --- | --- |
| `tree` | **tree_base** | 时钟树句柄 |

## 快捷函数

### config_reg

按树节点写寄存器。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 默认空则用 **sqr.tree** |

### check_measure

校验频率与占空比；一次 **start_measure** 并行观测。先确认有活动，再计数稳定周期。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 默认空则用 **sqr.tree** |
| **check_clk** | **bit** | `1` | 为真时检查 **clk** |
| **check_cell** | **bit** | `1` | 为真时检查 **cell** |
| **check_freq** | **bit** | `1` | 为真时检查 **clk/cell** 频率 |
| **check_duty** | **bit** | `1` | 为真时检查 **clk** 占空比；**cell** 不检查占空比 |
| **debug** | **bit** | `0` | 为真时 **check_measure** 打印等待进度 |

### test_measure

写寄存器后校验频率与占空比；一次 **check_measure** 并行观测。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 默认空则用 **sqr.tree** |
| **check_clk** | **bit** | `1` | 为真时检查 **clk** |
| **check_cell** | **bit** | `1` | 为真时检查 **cell** |
| **check_freq** | **bit** | `1` | 为真时检查 **clk/cell** 频率 |
| **check_duty** | **bit** | `1` | 为真时检查 **clk** 占空比；**cell** 不检查占空比 |
| **debug** | **bit** | `0` | 为真时 **check_measure** 打印等待进度 |

### test_flip

在器件输入端施加独立激励，检查 **gate/div/dto/mux/inv** 的寄存器控制功能。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 默认空则用 **sqr.tree** |
| **debug** | **bit** | `0` | 为真时打印测试开始信息 |

### test_route

驱动前级输出并采样后级输入，检查 RTL 连线。**clk/cell** 的单个 path 同时作为输入和输出；缺少接口的连线跳过。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 时钟树句柄；默认空则用 **sqr.tree** |
| **debug** | **bit** | `0` | 为真时打印测试开始信息 |
