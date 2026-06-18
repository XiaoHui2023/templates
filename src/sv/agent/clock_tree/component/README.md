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

校验频率与占空比；一次 **start_measure** 并行观测。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 默认空则用 **sqr.tree** |
| **check_freq** | **bit** | `1` | 为真时检查 **source**、**clk**、**pll** 频率 |
| **check_duty** | **bit** | `1` | 为真时检查全部带 **vif** 节点占空比 |

### test_measure

写寄存器后校验频率与占空比；一次 **check_measure** 并行观测。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 默认空则用 **sqr.tree** |
| **check_freq** | **bit** | `1` | 为真时检查 **source**、**clk**、**pll** 频率 |
| **check_duty** | **bit** | `1` | 为真时检查全部带 **vif** 节点占空比 |

### test_flip

写寄存器后校验 **div** / **dto** 复位翻转。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 默认空则用 **sqr.tree** |

### test_route

配置寄存器并遍历路由组合。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 时钟树句柄；默认空则用 **sqr.tree** |
| **always_active_clk_nodes** | **node_base** 队列 | 空队列 | 全程活动的 **clk** |
