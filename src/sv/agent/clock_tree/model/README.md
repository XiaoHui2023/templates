# 数据模型

## tree

### {name}_tree

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **nodes** | **node_base** 队列 | |
| **clock_nodes** | **clk** 队列 | |
| **{节点名}** | 节点类型或数组 | |

| 方法 | 说明 |
| --- | --- |
| **low_power** | 将非 **_always_active** 的 **clk** **enabled** 置 0 |
| **collect_always_active_clk_nodes** | 收集 **_always_active** 为真的 **clk** |
| **has_always_active_clk** | 是否存在 **_always_active** 为真的 **clk** |

| 约束 | 说明 |
| --- | --- |
| **cst_base** | 外部约束 |
| **cst_user** | 外部约束 |
| **cst_case** | 外部约束 |

## reg

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **field** | **uvm_reg_field** | 读写目标 field |
| **offset** | **int unsigned** | 在父寄存器中的位偏移 |
| **width** | **int unsigned** | 位宽 |
| **has_read** | **bit** | 是否已读过父寄存器 |

## 枚举

### pll_kind_e

| 取值 | 说明 |
| --- | --- |
| **PLL_TCI** | **pll_tci** |
| **PLL_SC** | **pll_sc** |
| **PLL_DW** | **pll_dw** |
| **PLL_INNO** | **pll_inno** |

### source_kind_e

| 取值 | 说明 |
| --- | --- |
| **SOURCE** | **source** |
| **PAD** | **source_pad** |
| **VDD** | **source_vdd** |
| **GND** | **source_gnd** |

## 节点

### source_base

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source_kind** | **source_kind_e** | 输入源型号 |
| **frequence** | **longint** | 频率 |
| **vif** | **interface** | 测量接口 |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |

| 约束 | 说明 |
| --- | --- |
| **cst_source** | **randomize** 后 **_resolved_freq** 等于 **frequence** |

### source

继承 **source_base**；构造时 **source_kind** 为 **SOURCE**。

### source_pad

继承 **source_base**；构造时 **source_kind** 为 **PAD**。

### source_vdd

继承 **source_base**；构造时 **source_kind** 为 **VDD**；**frequence** 固定为 0。

### source_gnd

继承 **source_base**；构造时 **source_kind** 为 **GND**；**frequence** 固定为 0。

### clk

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | 前级节点 |
| **vif** | **interface** | 测量接口 |
| **frequence** | **longint** | 频率 |
| **enabled** | **bit**，**rand** | 使能 |
| **_always_active** | **bit** | 全程保持有效；由树构造时按 YAML **always_active** 写入 |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_resolve_freq_from_src** | **source** 已连接时，**_resolved_freq** 等于 **source._resolved_freq** |
| **cst_clk** | **randomize** 后 **frequence** 等于 **_resolved_freq**，**enabled** 等于 **_resolved_active**；**_always_active** 为真时 **enabled** 必须为 1 |
| **post_randomize** | **randomize** 结束后 **_resolved_active** 为真且 **_resolved_freq** 低于 **min_freq_hz** 时 **uvm_fatal** |

### pll_tci

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | 参考时钟前级 |
| **vif** | **interface** | 测量接口 |
| **frequence** | **longint** | 频率 |
| **locked** | **bit** | 锁定状态 |
| **f_lock** | **reg** | |
| **f_bypass** | **reg** | |
| **f_pwrdn** | **reg** | |
| **f_reset** | **reg** | |
| **f_clkod** | **reg** | |
| **f_clkf** | **reg** | |
| **f_clkr** | **reg** | |
| **f_bwadj** | **reg** | |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_pll** | **randomize** 后 **_resolved_freq** 等于 **frequence**，不取 **source._resolved_freq** |

### pll_sc

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | 参考时钟前级 |
| **vif** | **interface** | 测量接口 |
| **frequence** | **longint** | 频率 |
| **locked** | **bit** | 锁定状态 |
| **f_lock** | **reg** | |
| **f_vocpd** | **reg** | |
| **f_postdivpd** | **reg** | |
| **f_dsmpd** | **reg** | |
| **f_pd** | **reg** | |
| **f_bypass** | **reg** | |
| **f_refdiv** | **reg** | |
| **f_postdiv2** | **reg** | |
| **f_postdiv1** | **reg** | |
| **f_fbdiv** | **reg** | |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_pll** | **randomize** 后 **_resolved_freq** 等于 **frequence**，不取 **source._resolved_freq** |

### pll_dw

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | 参考时钟前级 |
| **vif** | **interface** | 测量接口 |
| **frequence** | **longint** | 频率 |
| **locked** | **bit** | 锁定状态 |
| **f_lock** | **reg** | |
| **f_fbdiv** | **reg** | |
| **f_prediv** | **reg** | |
| **f_reset** | **reg** | |
| **f_pwron** | **reg** | |
| **f_shift** | **reg** | |
| **f_bypass** | **reg** | |
| **f_divvcor** | **reg** | |
| **f_r** | **reg** | |
| **f_p** | **reg** | |
| **f_divvcop** | **reg** | |
| **f_enr** | **reg** | |
| **f_enp** | **reg** | |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_pll** | **randomize** 后 **_resolved_freq** 等于 **frequence**，不取 **source._resolved_freq** |

### pll_inno

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **group_id** | **string** | 多路输出名；单路为空字符串 |
| **to_group** | **node_base** 关联数组 | 同组其它路节点 |
| **source** | **node_base** | 参考时钟前级 |
| **vif** | **interface** | 测量接口 |
| **frequence** | **longint** | 频率 |
| **locked** | **bit** | 锁定状态 |
| **f_lock** | **reg** | |
| **f_pd** | **reg** | |
| **f_refdiv** | **reg** | |
| **f_fbdiv** | **reg** | |
| **f_postdiv1** | **reg** | |
| **f_postdiv2** | **reg** | |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_pll** | **randomize** 后 **_resolved_freq** 等于 **frequence**，不取 **source._resolved_freq** |

### mux

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | 当前选中的前级节点 |
| **max_sel** | **int** | 最大选择值 |
| **sel** | **int**，**rand** | 当前选择值 |
| **to_source** | **node_base** 关联数组 | 各输入前级 |
| **f_reg** | **reg** | |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |

| 约束或回调 | 说明 |
| --- | --- |
| **cst_mux** | **sel** 只能取 0～**max_sel** 的整数 |
| **cst_resolve_active_from_src** | **to_source[sel]** 未连接时 **_resolved_active** 为 0；已连接时等于 **to_source[sel]._resolved_active** |
| **cst_resolve_freq_from_src** | **to_source[sel]** 已连接时 **_resolved_freq** 等于 **to_source[sel]._resolved_freq** |
| **post_randomize** | **randomize** 结束后将 **source** 设为 **to_source[sel]** |

### div_div

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | 前级节点 |
| **ratio** | **int**，**rand** | 分频比 |
| **f_rst** | **reg** | |
| **f_load** | **reg** | |
| **f_div** | **reg** | |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_div** | **ratio** 只能取 1～64 的整数 |
| **cst_resolve_freq_from_src** | **source** 已连接且 **ratio** 大于 0 时，**_resolved_freq** 落在 **source._resolved_freq** 整除 **ratio** 结果的 **period_tolerance** 相对偏差带内 |

### div_cpu_gate

继承 **div_base**；**div_kind** 为 **CPU_GATE**。YAML **regs** 只允许 **rst**、**div**，无 **load**。寄存器写序列按 **div_reg_high_means_reset** 解释 **rst** 极性，默认 **false** 表示 0 为复位、1 为不复位。

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **group_id** | **string** | 多路输出名 |
| **to_group** | **node_base** 关联数组 | 同节点其它路 |
| **source** | **node_base** | 前级节点 |
| **ratio** | **int**，**rand** | 分频比 |
| **f_rst** | **reg** | |
| **f_div** | **reg** | |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_div** | **ratio** 只能取 2、3、4、6 |
| **cst_resolve_freq_from_src** | **group_id** 为 **clk_arm_core** 时 **_resolved_freq** 等于 **source._resolved_freq**；其它路容差同 **div_base** |

### div_div_r

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | 前级节点 |
| **fixed_ratio** | **int** | 配置写入的固定分频比 |
| **ratio** | **int** | 等于 **fixed_ratio** |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_div** | **ratio** 等于 **fixed_ratio**，取值 1～64 |
| **cst_resolve_freq_from_src** | 继承 **div_base**，容差同 **div** |

### dto

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | 前级节点 |
| **ratio** | **int**，**rand** | 分频比 |
| **f_rst** | **reg** | |
| **f_load** | **reg** | |
| **f_bypass** | **reg** | |
| **f_step** | **reg** | |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_dto** | **ratio** 只能取 1～2^25 的正整数 |
| **cst_resolve_freq_from_src** | 继承 **div_base**，容差同 **div** |

### gate

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | 前级节点 |
| **_resolved_open** | **bit**，**rand** | 解析后的通行状态 |
| **open** | **int** | 配置输入；默认 -1 表示不参与固定；0 或 1 时约束 **_resolved_open** |
| **f_reg** | **reg** | |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |

| 约束 | 说明 |
| --- | --- |
| **cst_open** | **open** 为 0 或 1 时等于 **_resolved_open** |
| **cst_resolve_active_from_src** | **_resolved_open** 为 0 时 **_resolved_active** 为 0；为 1 且 **source** 已连接时等于 **source._resolved_active**；为 1 且 **source** 未连接时为 0 |
| **cst_resolve_freq_from_src** | **_resolved_open** 为 0 时 **_resolved_freq** 为 0；为 1 且 **source** 已连接时等于 **source._resolved_freq**；为 1 且 **source** 未连接时为 0 |

### cell

继承 **node_base**；**cell_kind** 仅作记录，不改变行为。

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | 前级节点 |
| **cell_kind** | **string** | 配置中的型号 |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_resolve_freq_from_src** | **source** 已连接时，**_resolved_freq** 等于 **source._resolved_freq** |

### inv

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | 前级节点 |
| **inverted** | **bit**，**rand** | 为真时反相输出 |
| **fix_inverted** | **bit** | 为真时固定 **inverted** |
| **f_reg** | **reg** | 反相/直通控制寄存器 |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_resolve_freq_from_src** | **source** 已连接时，**_resolved_freq** 等于 **source._resolved_freq** |
| **cst_inv** | **fix_inverted** 为真时 **inverted** 取固定值 |
