# 数据模型

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
| **frequence** | **longint** | 频率 |
| **vif** | **virtual interface** | 接口 |

| 约束 | 说明 |
| --- | --- |
| **cst_source** | 输出频率等于 **frequence** |

### clk

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | |
| **vif** | **virtual interface** | 接口 |
| **frequence** | **longint** | 频率 |
| **enabled** | **bit**，**rand** | |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 非空时同前级活动状态 |
| **cst_resolve_freq_from_src** | **source** 非空时同前级输出频率 |
| **cst_clk** | **frequence**、**enabled** 默认绑解析结果 |

### pll_tci

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | |
| **vif** | **virtual interface** | 接口 |
| **frequence** | **longint** | 频率 |
| **locked** | **bit** | |
| **f_lock** | 寄存器 field | |
| **f_bypass** | 寄存器 field | |
| **f_pwrdn** | 寄存器 field | |
| **f_reset** | 寄存器 field | |
| **f_clkod** | 寄存器 field | |
| **f_clkf** | 寄存器 field | |
| **f_clkr** | 寄存器 field | |
| **f_bwadj** | 寄存器 field | |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 非空时同前级活动状态 |
| **cst_pll** | 输出频率等于 **frequence** |

### pll_sc

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | |
| **vif** | **virtual interface** | 接口 |
| **frequence** | **longint** | 频率 |
| **locked** | **bit** | |
| **f_lock** | 寄存器 field | |
| **f_vocpd** | 寄存器 field | |
| **f_postdivpd** | 寄存器 field | |
| **f_dsmpd** | 寄存器 field | |
| **f_pd** | 寄存器 field | |
| **f_bypass** | 寄存器 field | |
| **f_refdiv** | 寄存器 field | |
| **f_postdiv2** | 寄存器 field | |
| **f_postdiv1** | 寄存器 field | |
| **f_fbdiv** | 寄存器 field | |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 非空时同前级活动状态 |
| **cst_pll** | 输出频率等于 **frequence** |

### pll_dw

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | |
| **vif** | **virtual interface** | 接口 |
| **frequence** | **longint** | 频率 |
| **locked** | **bit** | |
| **f_lock** | 寄存器 field | |
| **f_fbdiv** | 寄存器 field | |
| **f_prediv** | 寄存器 field | |
| **f_reset** | 寄存器 field | |
| **f_pwron** | 寄存器 field | |
| **f_shift** | 寄存器 field | |
| **f_bypass** | 寄存器 field | |
| **f_divvcor** | 寄存器 field | |
| **f_r** | 寄存器 field | |
| **f_p** | 寄存器 field | |
| **f_divvcop** | 寄存器 field | |
| **f_enr** | 寄存器 field | |
| **f_enp** | 寄存器 field | |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 非空时同前级活动状态 |
| **cst_pll** | 输出频率等于 **frequence** |

### pll_inno

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **group_id** | **int** | 多路输出路序号 |
| **to_group** | **node_base** 关联数组 | 多路输出时 |
| **source** | **node_base** | |
| **vif** | **virtual interface** | 接口 |
| **frequence** | **longint** | 频率 |
| **locked** | **bit** | |
| **f_lock** | 寄存器 field | |
| **f_pd** | 寄存器 field | |
| **f_refdiv** | 寄存器 field | |
| **f_fbdiv** | 寄存器 field | |
| **f_postdiv1** | 寄存器 field | 多路输出按下标展开 |
| **f_postdiv2** | 寄存器 field | 多路输出按下标展开 |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 非空时同前级活动状态 |
| **cst_pll** | 输出频率等于 **frequence** |

### mux

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | **post_randomize** 后为 **to_source[sel]** |
| **max_sel** | **int** | |
| **sel** | **int**，**rand** | |
| **to_source** | **node_base** 关联数组 | |
| **f_reg** | 寄存器 field | **reg** 配置时 |

| 约束或回调 | 说明 |
| --- | --- |
| **cst_mux** | **sel** 在 0～**max_sel** |
| **cst_resolve_active_from_src** | 重载：当前输入空则活动状态 0，否则同 **to_source[sel]** |
| **cst_resolve_freq_from_src** | 重载：当前输入非空则输出频率同该输入 |
| **post_randomize** | **to_source[sel]** 非空时 **source** 指向该输入 |

### div

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | |
| **ratio** | **int**，**rand** | |
| **f_rst** | 寄存器 field | |
| **f_load** | 寄存器 field | |
| **f_div** | 寄存器 field | |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 非空时同前级活动状态 |
| **cst_div** | **ratio** 为 1～64 |
| **cst_resolve_freq_from_src** | 重载：**source** 非空时输出频率为前级整除 **ratio** |

### dto

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | |
| **ratio** | **int**，**rand** | |
| **f_rst** | 寄存器 field | |
| **f_load** | 寄存器 field | |
| **f_bypass** | 寄存器 field | |
| **f_step** | 寄存器 field | |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 非空时同前级活动状态 |
| **cst_dto** | **ratio** 大于 0 且不超过 2^25 |
| **cst_resolve_freq_from_src** | 重载：**source** 非空时输出频率为前级整除 **ratio** |

### gate

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | |
| **open** | **bit**，**rand** | |
| **f_reg** | 寄存器 field | **reg** 配置时 |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | 重载：**open** 假则 0；真且 **source** 非空则同前级 |
| **cst_resolve_freq_from_src** | 重载：**open** 假或 **source** 空则 0；否则同前级 |

### inv

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **source** | **node_base** | |

| 约束 | 说明 |
| --- | --- |
| **cst_resolve_active_from_src** | **source** 非空时同前级活动状态 |
| **cst_resolve_freq_from_src** | **source** 非空时同前级输出频率 |

## tree

### {name}_tree

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **nodes** | **node_base** 队列 | |
| **clock_nodes** | **clk** 队列 | |
| **{节点名}** | 节点类型或数组 | |

| 约束 | 说明 |
| --- | --- |
| **cst_base** | 用户扩展 |
| **cst_user** | 用户扩展 |
| **cst_case** | 用户扩展 |

## reg

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **field** | **uvm_reg_field** | |
| **offset** | **int unsigned** | |
| **width** | **int unsigned** | |
| **has_read** | **bit** | |

配置寄存器模型且节点填写 **reg** 或 **regs** 时存在；节点 **f_*** 类型为 **reg**。
