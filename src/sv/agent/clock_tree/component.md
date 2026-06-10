# UVM 组件

![agent 与 kit_sequencer 结构](images/component_structure.drawio.svg)

## config_db

| 键 | 类型 | 说明 |
| --- | --- | --- |
| `tree` | **tree_base** | **build**、**connect_{name}_tree** 完成后写入 **agent**；**build_phase** 赋 **sqr.tree** |

## 快捷函数

**tree** 默认空则用 **sqr.tree**。

### config_reg

按树节点写寄存器模型。配置 **class_regmodel** 且节点绑定了 **regs** 时生成。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | |

### check_freq

量 **source**、**clk**、**pll** 频率。至少一处节点配置 **path** 时生成。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | |

### check_duty

量带 **vif** 节点占空比。至少一处节点配置 **path** 时生成。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | |

### test_freq

**config_reg** 后 **check_freq**。**path** 与 **regs** 均配置时生成。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | |

### test_duty

**config_reg** 后 **check_duty**。**path** 与 **regs** 均配置时生成。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | |

### test_flip

**div**、**dto** 分频比翻转探测。**route_test_enabled** 为真时生成。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | |

### test_route

路由组合结构探测。**route_test_enabled** 为真时生成。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | |
| **always_active_clk_nodes** | **node_base** 队列 | 空队列 | 全程活动的 **clk**；空为全部；**test_route** 开头 **config_reg** 后沿选通链定上游 **gate** / **mux** 并 **fix** 锁定；所列 **clk** **unfix_frequence** 为 1、**unfix_enabled** 为 0 |
