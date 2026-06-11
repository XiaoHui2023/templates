# 数据模型

## tree

### {name}_tree

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **nodes** | **node_base** 队列 | |
| **clock_nodes** | **clk** 队列 | |
| **{节点名}** | 节点类型或数组 | |

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
| **has_read** | **bit** | 已读过父寄存器则为 1 |

## 枚举

### pll_kind_e

| 取值 | 说明 |
| --- | --- |
| **PLL_TCI** | **pll_tci** |
| **PLL_SC** | **pll_sc** |
| **PLL_DW** | **pll_dw** |
| **PLL_INNO** | **pll_inno** |

## 节点

### source

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |
| **frequence** | **longint** | 频率 |
| **vif** | **interface** | 接口 |

| 约束 | 说明 |
| --- | --- |
| **cst_source** | **randomize** 后 **_resolved_freq** 等于 **frequence** |

### clk

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |
| **source** | **node_base** | |
| **vif** | **interface** | 接口 |
| **frequence** | **longint** | 频率 |
| **enabled** | **bit**，**rand** | |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_resolve_freq_from_src** | **source** 已连接时，**_resolved_freq** 等于 **source._resolved_freq** |
| **cst_clk** | **randomize** 后 **frequence** 等于 **_resolved_freq**，**enabled** 等于 **_resolved_active** |

### pll_tci

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |
| **source** | **node_base** | |
| **vif** | **interface** | 接口 |
| **frequence** | **longint** | 频率 |
| **locked** | **bit** | |
| **f_lock** | **reg** | |
| **f_bypass** | **reg** | |
| **f_pwrdn** | **reg** | |
| **f_reset** | **reg** | |
| **f_clkod** | **reg** | |
| **f_clkf** | **reg** | |
| **f_clkr** | **reg** | |
| **f_bwadj** | **reg** | |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_pll** | **randomize** 后 **_resolved_freq** 等于 **frequence**，不取 **source._resolved_freq** |

### pll_sc

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |
| **source** | **node_base** | |
| **vif** | **interface** | 接口 |
| **frequence** | **longint** | 频率 |
| **locked** | **bit** | |
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

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_pll** | **randomize** 后 **_resolved_freq** 等于 **frequence**，不取 **source._resolved_freq** |

### pll_dw

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |
| **source** | **node_base** | |
| **vif** | **interface** | 接口 |
| **frequence** | **longint** | 频率 |
| **locked** | **bit** | |
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

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_pll** | **randomize** 后 **_resolved_freq** 等于 **frequence**，不取 **source._resolved_freq** |

### pll_inno

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |
| **group_id** | **int** | 多路输出路序号 |
| **to_group** | **node_base** 关联数组 | 多路输出时 |
| **source** | **node_base** | |
| **vif** | **interface** | 接口 |
| **frequence** | **longint** | 频率 |
| **locked** | **bit** | |
| **f_lock** | **reg** | |
| **f_pd** | **reg** | |
| **f_refdiv** | **reg** | |
| **f_fbdiv** | **reg** | |
| **f_postdiv1** | **reg** | 多路输出按下标展开 |
| **f_postdiv2** | **reg** | 多路输出按下标展开 |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_pll** | **randomize** 后 **_resolved_freq** 等于 **frequence**，不取 **source._resolved_freq** |

### mux

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |
| **source** | **node_base** | **post_randomize** 后为 **to_source[sel]** |
| **max_sel** | **int** | |
| **sel** | **int**，**rand** | |
| **to_source** | **node_base** 关联数组 | |
| **f_reg** | **reg** | |

| 约束或回调 | 说明 |
| --- | --- |
| **cst_mux** | **sel** 只能取 0～**max_sel** 的整数 |
| **cst_resolve_active_from_src** | **to_source[sel]** 未连接时 **_resolved_active** 为 0；已连接时等于 **to_source[sel]._resolved_active** |
| **cst_resolve_freq_from_src** | **to_source[sel]** 已连接时 **_resolved_freq** 等于 **to_source[sel]._resolved_freq** |
| **post_randomize** | **randomize** 结束后将 **source** 设为 **to_source[sel]** |

### div

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |
| **source** | **node_base** | |
| **ratio** | **int**，**rand** | |
| **f_rst** | **reg** | |
| **f_load** | **reg** | |
| **f_div** | **reg** | |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_div** | **ratio** 只能取 1～64 的整数 |
| **cst_resolve_freq_from_src** | **source** 已连接时，**_resolved_freq** 等于 **source._resolved_freq** 整除 **ratio** |

### dto

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |
| **source** | **node_base** | |
| **ratio** | **int**，**rand** | |
| **f_rst** | **reg** | |
| **f_load** | **reg** | |
| **f_bypass** | **reg** | |
| **f_step** | **reg** | |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_dto** | **ratio** 只能取 1～2^25 的正整数 |
| **cst_resolve_freq_from_src** | **source** 已连接时，**_resolved_freq** 等于 **source._resolved_freq** 整除 **ratio** |

### gate

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |
| **source** | **node_base** | |
| **open** | **bit**，**rand** | |
| **f_reg** | **reg** | |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **open** 为 0 时 **_resolved_active** 为 0；**open** 为 1 且 **source** 已连接时等于 **source._resolved_active**；**open** 为 1 且 **source** 未连接时为 0 |
| **cst_resolve_freq_from_src** | **open** 为 0 时 **_resolved_freq** 为 0；**open** 为 1 且 **source** 已连接时等于 **source._resolved_freq**；**open** 为 1 且 **source** 未连接时为 0 |

### inv

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **_resolved_freq** | **longint**，**rand** | 输出频率 |
| **_resolved_active** | **bit**，**rand** | 活动状态 |
| **source** | **node_base** | |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 已连接时，**_resolved_active** 等于 **source._resolved_active** |
| **cst_resolve_freq_from_src** | **source** 已连接时，**_resolved_freq** 等于 **source._resolved_freq** |
