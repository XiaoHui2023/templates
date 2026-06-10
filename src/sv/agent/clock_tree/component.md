# UVM 组件

![agent 与 kit_sequencer 结构](images/component_structure.drawio.svg)

## config_db

| 键 | 类型 | 说明 |
| --- | --- | --- |
| `tree` | **tree_base** | 测试平台创建 **tree**、**build** 绑定寄存器模型、**connect_{name}_tree** 挂 **vif** 后写入 **agent**；**build_phase** 赋给 **sqr.tree** |

## 快捷函数

在 **agent.sqr** 上调用同名 **task**；失败则中止。

### config_reg

按树节点把目标值写入寄存器模型。配置 **class_regmodel** 且节点绑定了 **regs** 时才会生成。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 待处理整棵树；空则用 **sqr.tree** |

### check_freq

量 **source**、**clk**、**pll** 波形频率，与节点 **frequence** 比较。至少一处节点配置 **path** 时才会生成。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 待量测整棵树；空则用 **sqr.tree** |

### check_duty

量带 **vif** 节点的占空比，与 **settings** 中 **duty_min**、**duty_max** 闭区间比较。至少一处节点配置 **path** 时才会生成。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 待量测整棵树；空则用 **sqr.tree** |

### test_freq

先 **config_reg**，再 **check_freq**。**path** 与 **regs** 均配置时才会生成。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 待测整棵树；空则用 **sqr.tree** |

### test_duty

先 **config_reg**，再 **check_duty**。**path** 与 **regs** 均配置时才会生成。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 待测整棵树；空则用 **sqr.tree** |

### test_flip

写寄存器后对 **div**、**dto** 做分频比翻转探测。**route_test_enabled** 为真时才会生成。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 待测整棵树；空则用 **sqr.tree** |

### test_route

写寄存器后遍历路由组合做结构探测。**route_test_enabled** 为真时才会生成。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 待测整棵树；空则用 **sqr.tree** |
| **always_active_clk_nodes** | **node_base** 队列 | 空队列 | 须全程保持活动的 **clk** 节点；空则要求全部 **clk** 活动；探测时只固定其 **enabled** |
