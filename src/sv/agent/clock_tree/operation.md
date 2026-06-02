# operation

时钟树 **agent** 在 **kit_sequencer** 上提供与 **sequence/operation** 目录同名的 **task**。测试平台在 **agent.sqr** 上调用；**nodes** 默认为空队列时表示对该 **tree** 的全部节点生效。

## 调用约定

| 项 | 说明 |
| --- | --- |
| 入口 | **kit_sequencer** 上与操作同名的 **task** |
| **nodes** | 空队列时对 **tree.nodes** 整棵执行；非空时只处理列表中的节点 |
| **set_clock_gen** | **kit** 对每个带 **vif** 的节点各 **start** 一次底层序列 |
| 其余操作 | 一次 **start**，**req.nodes** 携带整批节点 |

至少一处节点配置了 **path** 才会生成 **set_clock_gen** 与三项 **check_***。配置 **class_regmodel** 且节点绑定了 **regs** 时才会生成 **config_reg**。

## 操作一览

| 名称 | 作用 |
| --- | --- |
| **set_clock_gen** | 按节点 **frequence** 打开或关闭 **vif** 上的时钟发生器 |
| **config_reg** | 把 **gate**、**mux**、**div**、**dto**、**pll** 的目标值写入 RAL |
| **check_clk** | 测量 **clk** 波形频率，与节点 **frequence** 比较 |
| **check_pll** | 测量 **pll** 波形频率，与节点 **frequence** 比较 |
| **check_duty** | 测量带 **vif** 节点的占空比，与 **duty_min**、**duty_max** 比较 |

容差与占空比上下限在 **settings** 的 **period_tolerance**、**duty_min**、**duty_max**；PLL 等锁超时为 **pll_lock_timeout_us**。

## set_clock_gen

**gen_en** 为 1 时要求 **frequence** 为正，并向 **vif** 写入该频率；为 0 时关闭发生器。

## config_reg

通过 **sequencer.tools** 写 RAL，只更新约定 field，field 内其余位保持不变。

写入分五段，与 **req.nodes** 下标无关：

1. 全部 **pll** 寄存器，再对本轮全部 **pll** **wait_lock**
2. 全部 **div**、**dto**
3. **open** 为真的 **gate**
4. 全部 **mux**
5. **open** 为假的 **gate**

**pll** 分频用 **source.frequence** 与节点 **frequence**；缺 **source** 或频率非法则 **fatal**。

## check_clk

只处理 **req.nodes** 里类型为 **clk** 且已挂 **vif** 的项。开启测量、等待 **stable**，再比较测得频率与 **frequence**；超出 **period_tolerance** 则报错。

## check_pll

与 **check_clk** 相同，对象改为 **pll** 节点。

## check_duty

处理 **req.nodes** 里已挂 **vif** 的节点，不限 **kind**。等待 **stable** 后根据 **vif.meas.duty_ok** 判定；范围由 **duty_min**、**duty_max** 决定。
