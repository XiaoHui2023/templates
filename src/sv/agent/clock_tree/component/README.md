# UVM 组件

agent 包含 kit_sequencer 实例 `sqr`，提供配置和检查入口。

## config_db

| 键 | 类型 | 说明 |
| --- | --- | --- |
| `tree` | **tree** | 时钟树句柄，类型名前缀与 agent 一致 |

## 快捷函数

### config_reg

按树节点写寄存器。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 默认空则用 **sqr.tree** |

### check_measure

检查活动、频率与占空比。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 默认空则用 **sqr.tree** |
| **check_observation** | **bit** | `1` | 为真时检查所有可观测节点 |
| **check_freq** | **bit** | `1` | 为真时检查可观测节点频率 |
| **check_duty** | **bit** | `1` | 为真时检查声明占空比能力的节点 |

### test_measure

配置寄存器后检查活动、频率与占空比。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 默认空则用 **sqr.tree** |
| **check_observation** | **bit** | `1` | 为真时检查所有可观测节点 |
| **check_freq** | **bit** | `1` | 为真时检查可观测节点频率 |
| **check_duty** | **bit** | `1` | 为真时检查声明占空比能力的节点 |

### test_flip

检查节点插件提供的寄存器功能。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 默认空则用 **sqr.tree** |

### test_route

检查器件之间的 RTL 连线。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 时钟树句柄；默认空则用 **sqr.tree** |
