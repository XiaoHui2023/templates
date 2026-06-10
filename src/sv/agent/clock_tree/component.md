# UVM 组件

![](images/component_structure.drawio.svg)

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

### check_freq

校验各 **clk** 频率。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 默认空则用 **sqr.tree** |

### check_duty

校验各 **clk** 占空比。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 默认空则用 **sqr.tree** |

### test_freq

写寄存器后校验各 **clk** 频率。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 默认空则用 **sqr.tree** |

### test_duty

写寄存器后校验占空比。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | 空 | 默认空则用 **sqr.tree** |

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
