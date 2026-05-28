# 数据模型

展开类型名带 **class_prefix** 前缀；下文标题与表仅用后缀名。

## 类型继承

配置中的每棵 **tree** 展开为 **`{name}_tree`** 类型，挂在 **base_tree** 下；节点类型均派生 **node_base**。

```mermaid
classDiagram
    uvm_sequence_item <|-- spec_item
    spec_item <|-- base_item
    base_item <|-- node_base
    base_item <|-- settings
    base_item <|-- base_tree
    node_base <|-- source
    node_base <|-- clk
    node_base <|-- pll
    node_base <|-- mux
    node_base <|-- div
    node_base <|-- dto
    node_base <|-- gate
    node_base <|-- inv
    base_tree <|-- tree_impl
```

**spec_item** 即 **spec** 以 **uvm_sequence_item** 为类型实参的展开名。**tree_impl** 表示各配置树类型，如 **main_tree**。

## pll_kind_e

| 取值 | 说明 |
| --- | --- |
| PLL_TCI | PLL 型号 |
| PLL_SC | PLL 型号 |
| PLL_DW | PLL 型号 |

## node_base

各类时钟树节点的公共字段。

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| kind | string | 器件类型；各派生类在 **new** 中设为配置 **kind** 字面量 |
| allow_bad_duty | bit，rand | 为真时放宽占空比检查；**node_base** 软约束默认为 0，配置为真时 **tree** 软约束为 1 |
| frequence | longint，rand | 典型频率，单位 Hz；**cst_node_base** 软约束默认为 0 |
| valid | bit，rand | 时钟是否有效；**cst_node_base** 软约束默认为 0 |
| vif | virtual interface | 配置中填写 RTL 路径时由 **connection** 绑定对应 interface；未配置则为 null |
| source | 节点句柄 | 前级驱动；无配置则为 null |
| cst_clk_from_src | 约束 | 前级非空时 **valid** 与前级一致；子类可重载 |
| cst_freq_from_src | 约束 | 前级非空时 **frequence** 与前级一致；子类可重载或空关断 |

## base_tree

整棵时钟树的节点容器。

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| nodes | 节点队列 | 建树后装入的全部节点句柄 |
| low_power | bit，rand | 低功耗；软约束默认为 0。**cst_base_tree** 在 **low_power** 为 0 时将 **nodes** 中 **kind** 为 **gate** 的 **valid** 软约束为 1，为 1 时软约束为 0 |
| settings | settings | 仅声明 **setting_defs** 时存在 |

## source

配置 **kind: source** 的时钟根节点；无前级时 **cst_freq_from_src** 不施加频率等式，频率由 **tree** 软约束或随机。**cst_source**：**frequence** 大于 0 时 **valid** 为 1。

## clk

观测用时钟节点；**valid** 可随机，有前级时随 **cst_clk_from_src** 与前级一致。

## pll

PLL 节点；空关断 **cst_freq_from_src**，频率由 **tree** 软约束指向配置典型值。**cst_pll**：**frequence** 大于 0 时 **valid** 为 1。

| 成员 / 配置 | 类型 | 说明 |
| --- | --- | --- |
| pll_kind | pll_kind_e | PLL 型号 |
| locked | bit | 锁定指示 |
| regs | 映射，可选 | 键须落在该 **pll_kind** 允许集合内；路径写法同 **div** |

| pll_kind | 允许 regs 键 |
| --- | --- |
| PLL_TCI | lock、bypass、ndiv、fdiv、pd |
| PLL_SC | lock、en、mult |
| PLL_DW | lock、pwdn、m、n、od |

## mux

多路选择节点。

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| sel | int，rand | 选择值；**cst_base** 中 **inside** 与软约束与配置一致 |
| to_source | 关联数组，int 键 | 各输入前级；**post_randomize** 在 **to_source[sel] != null** 时写入 **source** |

**cst_clk_from_src**：**to_source[sel]** 为空则 **valid** 为 0，否则随所选前级 **valid**。

## div

分频节点。

| 成员 / 配置 | 说明 |
| --- | --- |
| ratio | 分频比，rand，默认 1，须大于 0 |
| regs | 可选；逻辑名 **ratio**、**enable**、**bypass** 对应 **uvm_reg_field**；值为自 RAL 根起的点分路径，或一层 block 名下挂 field 短名 |

**cst_div**：**ratio** 须大于 0；重载 **cst_freq_from_src**，前级频率整除 **ratio**。

## dto

占空比变换节点。

| 成员 / 配置 | 说明 |
| --- | --- |
| ratio | 分频比，rand，默认 1，须大于 0 |
| regs | 可选；逻辑名 **ratio**、**duty**、**enable**、**bypass**；路径写法同 **div** |

频率约束同 **div**。

## gate

门控节点。

| 成员 / 配置 | 类型 | 说明 |
| --- | --- | --- |
| open | bit，rand | 为真时开放时钟通行；为假时屏蔽输出 |
| reg_gate | string，可选 | 门控 field 点分路径；省略表示无寄存器 |

重载 **cst_clk_from_src**：前级有效且 **open** 为真时 **valid** 为真。

## inv

反相器节点；除 **node_base** 公共字段外无附加成员。
