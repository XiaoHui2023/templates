# 数据模型

展开类型名带 **class_prefix** 前缀；下文标题与表仅用后缀名。

## 枚举类型

| 枚举 | 取值 | 说明 |
| --- | --- | --- |
| pll_kind_e | PLL_TCI、PLL_SC、PLL_DW | PLL 型号 |

## node_base

各类时钟树节点的公共字段。

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| name | string | 节点名，与配置一致 |
| path | string | 对应信号实例层次路径；留空则不接 **in**，**out** 变化 **uvm_fatal** |
| allow_bad_duty | bit | 为真时放宽占空比检查 |
| frequence | longint | 典型频率，单位 Hz，rand |
| clk_on | bit，rand | 当前节点时钟是否有效；无前级时由子类约束 |
| vif | virtual interface | 测量 interface 句柄 |
| source | 节点句柄 | 前级驱动；无配置则为 null |
| cst_clk_from_src | 约束 | 前级非空时 **clk_on** 与前级一致 |
| cst_freq_from_src | 约束 | 前级非空时 **frequence** 与前级一致 |

## source

配置 **kind: source** 的时钟根节点；**clk_on** 恒为 1；无上游时关闭 **cst_freq_from_src**，频率由 **tree** 软约束或随机。

## clk

观测用时钟节点；**clk_on** 恒为 1。

## pll

PLL 节点；关闭 **cst_freq_from_src**，频率仍由 tree 软约束指向配置典型值。

| 成员 / 配置 | 类型 | 说明 |
| --- | --- | --- |
| kind | pll_kind_e | PLL 型号 |
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
| sel | int | 选择值 |
| to_source | 关联数组，int 键 | 各输入前级；**post_randomize** 按 **sel** 写入 **source** |

## div

分频节点。

| 成员 / 配置 | 说明 |
| --- | --- |
| div_ratio | 分频比，默认 1 |
| regs | 可选；逻辑名 **ratio**、**enable**、**bypass** 对应 **uvm_reg_field**；值为自 RAL 根起的点分路径，或一层 block 名下挂 field 短名 |

覆盖 **cst_freq_from_src**：前级频率整除 **div_ratio**。

## dto

占空比变换节点。

| 成员 / 配置 | 说明 |
| --- | --- |
| div_ratio | 分频比，默认 1 |
| regs | 可选；逻辑名 **ratio**、**duty**、**enable**、**bypass**；路径写法同 **div** |

频率约束同 **div**。

## gate

门控节点。

| 成员 / 配置 | 类型 | 说明 |
| --- | --- | --- |
| gate | bit | 门控开关 |
| reg_gate | string，可选 | 门控 field 点分路径；省略表示无寄存器 |

覆盖 **cst_clk_from_src**：前级有效且 **gate** 为真时 **clk_on** 为真。

## inv

反相器节点。

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| inv | bit | 反相使能 |

## wire

直通节点，无附加字段。

## interface

每节点对应一个 **interface** 实例，内含 **generate_interface** 与 **measure_interface** 子实例；时间单位为 **1ns**、精度 **1fs**。配置 **path** 非空时 **in** 接该层次路径，**out** 由 **connection** 对该路径 **force** 或 **release**；测量读 **meas** 子实例。配置 **path** 留空时 **in** 不接 DUT，**out** 变化 **uvm_fatal**。

| 成员 / 方法 | 说明 |
| --- | --- |
| **gen** | 时钟发生子 **interface**；**out** 由顶层 **out** 引出 |
| gen.gen_en | 发生开关，初值为 0；为 0 时不驱动方波，发生任务阻塞等待 |
| gen.gen_hz | 发生频率，单位 Hz |
| gen.set_clock_gen | 设置 **gen_en** 与 **gen_hz** |
| set_clock_gen | 转调 **gen.set_clock_gen** |
| **meas** | 测量子 **interface**；**in** 接顶层 **in** |
| meas.meas_en | 测量总开关，初值为 0；为 0 时不采样边沿、不跑超时循环 |
| meas.set_measure_en | 设置 **meas_en**；关时清零测量结果 |
| set_measure_en | 转调 **meas.set_measure_en** |
| meas.active、meas.freq_hz、meas.duty、meas.stable 等 | **meas_en** 为 1 时对 **in** 边沿测量 |
| **out** | **gen.gen_en** 为 1 时等于 **gen.gen_clk**；为 0 时为高阻 |

## spec 与 base_item

**spec** 为参数化壳类 **`spec#(type T)`**，**extends T**，用于在继承链上集中放置 **enum** 与 **typedef enum**。**base_item** 派生 **spec#(uvm_sequence_item)**，承载 **pll_kind_e** 等族级枚举。

## base_tree

各棵时钟树类型的公共基类；含 **nodes** 队列。声明 **setting_defs** 时含 **settings** 成员。

## 各 tree 类型

配置中每棵 **tree** 展开为 **`{name}_tree`** 类，平铺 **rand** 节点成员；**new** 中创建 **settings** 并按 YAML **settings** 字典逐字段赋值；**nodes** 队列在 **base_tree**；**cst** 对 **source**、**clk** 与 **pll** 的典型频率做软约束，并预留 **cst_user**、**cst_case**。

## settings

设置数据包；字段由 **setting_defs** 声明；每棵 **tree** 在 **new** 中例化并赋值，通过 **base_tree.settings** 访问。

## class_regmodel

RAL 根块类型名。任一节点的寄存器路径非空时必填。**connection** 中 **`build_{tree}_tree`** 与 **`build_all_trees`** 以此类型接收 **regmodel**，并按配置路径把 **uvm_reg_field** 绑到对应节点成员。

## 寄存器绑定

展开后 **div** / **dto** / **pll** 上为 **`{逻辑名}_rf`**，**gate** 为 **reg_gate_f**。配置写了路径且 **regmodel** 非 null 时，在 **connect** 阶段赋值。
