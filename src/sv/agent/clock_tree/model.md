# 数据模型

展开类型名带 **class_prefix** 前缀；下文标题与表仅用后缀名。

## 类型继承

配置中的每棵 **tree** 展开为 **`{name}_tree`** 类型，挂在 **tree_base** 下；节点类型均派生 **node_base**。

```mermaid
classDiagram
    uvm_sequence_item <|-- spec_item
    spec_item <|-- base_item
    base_item <|-- node_base
    base_item <|-- tree_base
    node_base <|-- source
    node_base <|-- clk
    node_base <|-- pll_base
    pll_base <|-- pll_tci
    pll_base <|-- pll_sc
    pll_base <|-- pll_dw
    node_base <|-- mux
    node_base <|-- div
    node_base <|-- dto
    node_base <|-- gate
    node_base <|-- inv
    tree_base <|-- tree_impl
```

**spec_item** 即 **spec** 以 **uvm_sequence_item** 为类型实参的展开名。**tree_impl** 表示各配置树类型，如 **main_tree**。

## node_base

各类时钟树节点的公共字段。

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| kind | string | 器件类型；各派生类在 **new** 中设为配置 **kind** 字面量 |
| frequence | longint，rand | 典型频率，单位 Hz；**cst_node_base** 软约束默认为 0 |
| valid | bit，rand | 时钟是否有效；**cst_node_base** 软约束默认为 0 |
| vif | virtual interface | 配置中填写 RTL 路径时由 **tree_connection** 绑定对应 interface；未配置则为 null |
| source | 节点句柄 | 前级驱动；无配置则为 null |
| cst_resolve_active_from_src | 约束 | 前级非空时 **valid** 与前级一致；子类可重载 |
| cst_resolve_freq_from_src | 约束 | 前级非空时 **frequence** 与前级一致；子类可重载或空关断 |

## tree_base

整棵时钟树的节点容器。

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| nodes | 节点队列 | 建树后装入的全部节点句柄 |
| low_power | bit，rand | 低功耗；软约束默认为 0。**cst_tree_base** 在 **low_power** 为 0 时将 **nodes** 中 **kind** 为 **clk** 的 **valid** 软约束为 1，为 1 时软约束为 0 |

## 图遍历

**core/tree_nodes.sv** 提供 **function automatic** 工具，入参为 **tree_base** 与 **tree.nodes** 中的节点句柄；结果不含入参节点本身。**mux** 按 **to_source** 全输入展开，不只当前 **sel**。

| 函数 | 说明 |
| --- | --- |
| **get_nodes_before** | 沿 **source** / **to_source** 向上收集全部前级节点；可选 **kind** 实参，空串表示不过滤 |
| **get_nodes_after** | 在 **tree.nodes** 中收集以该节点为前级的全部后级节点；可选 **kind** 同上 |
| **get_tree_head_nodes** | 在 **tree.nodes** 中取开端节点：无前级，或全部前级不在 **tree.nodes**；**mux** 任一 **to_source** 落在 **tree.nodes** 则不算开端 |
| **get_tree_tail_nodes** | 在 **tree.nodes** 中取末尾节点：无后级，或全部后级不在 **tree.nodes** |
| **get_subgraph_tail_nodes** | 在入参节点队列内按末尾规则筛选；须传入 **tree_base** 供下游扫描 |
| **filter_nodes_by_kind** | 按 **kind** 字符串筛选节点队列；**kind** 为空串时原样返回 |
| **get_sources_before** / **get_clks_before** / **get_plls_before** 等 | 固定 **kind** 封装；后级方向同名，如 **get_plls_after** |
| **get_sources_at_tree_head** / **get_clks_at_tree_tail** 等 | 在整棵树开端或末尾按 **kind** 筛选 |

## source

配置 **kind: source** 的时钟根节点；无前级时 **cst_resolve_freq_from_src** 不施加频率等式。**classic_frequence** 由建树 **new** 从 YAML **freq** 写入；**cst_source** 硬约束 **frequence** 等于 **classic_frequence**；**frequence** 大于 0 时 **valid** 为 1。

## clk

观测用时钟节点。**cst_clk** 将 **frequence**、**enabled** 分别与 **_resolved_freq**、**_resolved_active** 绑定；**unfix_frequence**、**unfix_enabled** 为 1 时对应等式不施加，为 0 时该字段随解析结果固定、不独立随机。

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| frequence | longint | 频率，单位 Hz |
| enabled | bit，rand | 是否活动 |
| unfix_frequence | bit | **enable_node_fix** 为真时生成；为 1 时 **cst_clk** 不约束 **frequence**；由序列或环境赋值，不可由 YAML 配置 |
| unfix_enabled | bit | **enable_node_fix** 为真时生成；为 1 时 **cst_clk** 不约束 **enabled**；由序列或环境赋值，不可由 YAML 配置 |

## pll_base

PLL 公共基类；**kind** 在 **new** 中固定为 **pll**。**classic_frequence** 由建树 **new** 写入；**cst_pll** 约束 **frequence** 等于 **_resolved_freq**；**cst_resolve_freq_from_src** 空关断，输出频率由 **frequence** 直接给定，须按前级换算时由序列或环境先读前级频率再写入 **frequence**。**config_reg** 以 **source.frequence** 为参考时钟算分频，**source** 为 null 则 **uvm_fatal**；**valid** 为 0 时跳过寄存器更新与 **wait_lock**；参考频率与 **frequence** 均与 **pll_cfg** 中上次写入记录相同时亦跳过寄存器更新。**cst_pll**：**frequence** 大于 0 时 **valid** 为 1。

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| pll_kind | pll_kind_e | 各 **pll_*** 子类在 **new** 中赋固定枚举值 |
| locked | bit | 锁定指示 |

YAML **pll_kind** 决定 **tree** 例化 **pll_tci**、**pll_sc**、**pll_dw** 中的哪一类，并与 **regs** 允许键校验一致；展开后 **pll_kind** 成员与之类型一致。

| 配置 pll_kind | 展开类型 | 说明 |
| --- | --- | --- |
| tci | pll_tci | TCI 寄存器在该类 |
| sc | pll_sc | SC 寄存器在该类 |
| dw | pll_dw | DW 寄存器在该类 |

| 配置 / 成员 | 类型 | 说明 |
| --- | --- | --- |
| source | str，必填 | 参考时钟前级节点名；**tree** 构造时写入 **source** 句柄 |
| pll_kind | tci、sc、dw，必填，大小写不限 | 决定例化哪一类 **pll_*** |
| regs | dict，可选 | 键为逻辑名、值为 寄存器模型路径，按 `.` 分隔，可带 `[n]` 或 `[msb:lsb]` 后缀；**非空时须与 pll_kind 允许名字完全一致**，不得缺键或多键 |

| pll_kind | regs 须包含的键 |
| --- | --- |
| tci | lock、bypass、pwrdn、reset、clkod、clkf、clkr、bwadj |
| sc | lock、vocpd、postdivpd、dsmpd、pd、bypass、refdiv、postdiv2、postdiv1、fbdiv |
| dw | lock、fbdiv、prediv、reset、pwron、shift、bypass、divvcor、r、p、divvcop、enr、enp |

## mux

多路选择节点。

| 成员 / 配置 | 类型 | 说明 |
| --- | --- | --- |
| sel | int，rand | 选择值；**cst_mux** 约束 **sel** 在 0 至 **max_sel** |
| max_sel | int | 建树时由 **mux.source** 键最大值写入 |
| fix_sel | int | **enable_node_fix** 为真时生成；默认 **-1** 表示不固定 **sel**；**≥ 0** 时在 **cst_resolve_active_from_src** 中约束 **sel** 等于该值 |
| to_source | 关联数组，int 键 | 各输入前级；**post_randomize** 在 **to_source[sel] != null** 时写入 **source** |
| reg | string，可选 | 寄存器模型路径，按 `.` 分隔，可带比特范围后缀；**config_reg** 写入 **sel** |

**cst_resolve_active_from_src**：**to_source[sel]** 为空则 **valid** 为 0，否则随所选前级 **valid**。

## enable_node_fix

**Models** 推导字段：分别存在非空 **path** 节点与非空 **reg** 或 **regs** 节点时为真。为真时在 **gate**、**mux**、**div**、**dto** 模型类中生成 **fix_*** 成员，在 **clk** 中生成 **unfix_frequence**、**unfix_enabled**；YAML 不可写入 **settings**。

## div

分频节点。

| 成员 / 配置 | 说明 |
| --- | --- |
| ratio | 分频比，rand，须 1～64；1 表示不分频，大于 1 表示分频比为 **ratio** |
| fix_ratio | int | **enable_node_fix** 为真时生成；默认 **0** 表示不固定分频比；**> 0** 时在 **cst_div** 中约束 **ratio**；由序列或环境在 **config_reg** 调用前赋值，不可经 YAML 配置 |
| regs | 映射，可选 | 非空时键为 rst、load、div，值为各 field 的 寄存器模型路径，按 `.` 分隔，可带比特范围后缀 |

**cst_div**：**ratio** 在 1～64；**cst_resolve_freq_from_src** 为前级频率整除 **ratio**。

**config_reg**：节点**首次**配置时 **rst** 写复位电平；**div** 写 N，N=0 不分频，N>0 时分频比为 N+1；**load** 先写 0 再写 1；**rst** 写不复位电平。为真时 **div_reg_high_means_reset** 复位为 1、不复位为 0；为假则复位为 0、不复位为 1。同一 **sequencer** 上该节点已释放过 **rst** 后，**config_reg** 与 **configure_div_ratio** 相同，只改 **div** 与 **load**。

## dto

占空比变换节点。

| 成员 / 配置 | 说明 |
| --- | --- |
| ratio | 分频比，rand，须大于 0 且不超过 2^25；与 **step** 对应关系为 分频比 = 2^25 / **step** |
| fix_ratio | int | **enable_node_fix** 为真时生成；默认 **0** 表示不固定分频比；**> 0** 时在 **cst_dto** 中约束 **ratio**；由序列或环境在 **config_reg** 调用前赋值，不可经 YAML 配置 |
| regs | 可选；非空时键须为 **rst**、**load**、**bypass**、**step**，值为各 field 的 寄存器模型路径，按 `.` 分隔，可带比特范围后缀 |

**cst_dto**：**ratio** 大于 0 且不超过 2^25；**cst_resolve_freq_from_src** 为前级频率整除 **ratio**。

**config_reg**：节点**首次**配置时 **rst** 写复位电平；**load**=1，**bypass**=0，**step**=2^25/**ratio**（整数，须落在 1～2^25−1，故 **ratio** 不能为 1）；**rst** 写不复位电平。为真时 **dto_reg_high_means_reset** 复位为 1、不复位为 0；为假则复位为 0、不复位为 1。同一 **sequencer** 上该节点已释放过 **rst** 后，**config_reg** 与 **configure_dto_ratio** 相同，只改 **step**、**load**、**bypass**。

## gate

门控节点。

| 成员 / 配置 | 类型 | 说明 |
| --- | --- | --- |
| open | bit，rand | 为真时开放时钟通行；为假时屏蔽输出 |
| fix_open | bit | **enable_node_fix** 为真时生成；为 1 时在 **cst_gate** 中约束 **open** 为 1 |
| fix_close | bit | **enable_node_fix** 为真时生成；为 1 时在 **cst_gate** 中约束 **open** 为 0 |
| reg | string，可选 | 寄存器模型路径，按 `.` 分隔，可带比特范围后缀；**config_reg** 写入门控位，写 1 是否表示打开由 **settings** 的 **gate_reg_high_means_open** 决定 |

重载 **cst_resolve_active_from_src**：**open** 为假时 **valid** 为 0；**open** 为真且前级非空时 **valid** 与前级一致；**open** 为真且无前级时 **valid** 为 0。重载 **cst_resolve_freq_from_src**：**open** 为假时 **frequence** 为 0；**open** 为真且前级非空时 **frequence** 与前级一致；**open** 为真且无前级时 **frequence** 为 0。

## inv

反相器节点；除 **node_base** 公共字段外无附加成员。
