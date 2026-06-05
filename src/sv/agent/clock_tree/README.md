# clock_tree

## 示例

```yaml
trees:
  - name: main
    nodes:
      osc:
        kind: source
      pll0:
        kind: pll
        source: osc
        pll_kind: tci
        freq: 1000000000
      clk_cpu:
        kind: clk
        source: pll0
settings:
  class_prefix: chip_clk_
```

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `trees` | `list[Tree]` | 必填 | 时钟树。 |
| `settings` | `Settings` | 见下表 | 全局选项。 |
| `enable_node_fix` | `bool` | — | 推导字段，不可传入；分别存在填写 `path` 的节点与填写 `reg` 或 `regs` 的节点时为真，为真时生成各节点 **fix_*** 成员。 |

### Settings

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `class_prefix` | `str` | `clk_tree_` | 命名前缀。 |
| `class_regmodel` | `str` | 空 | 寄存器模型类型名；须与至少一处节点 `reg` 或 `regs` 同时填写，才生成寄存器访问与 **config_reg**。 |
| `min_freq_hz` | `int` | `500` | 判断时钟仍在活动的最低频率。 |
| `stable_cycles` | `int` | `3` | 连续稳定周期数。 |
| `period_tolerance` | `float` | `0.05` | 相邻周期相对偏差上限。 |
| `duty_min` | `float` | `0.50` | 允许占空比下限；至少一处节点填写 `path` 时供 **check_duty** 使用。 |
| `duty_max` | `float` | `0.66` | 允许占空比上限；至少一处节点填写 `path` 时供 **check_duty** 使用。 |
| `pll_lock_timeout_us` | `int` | `1000` | **config_reg** 等待各 PLL lock 的最长时间，微秒。 |
| `pll_sc_fbdiv_min` | `int` | `16` | 允许 PLL SC FBDIV 下限。 |
| `pll_sc_fbdiv_max` | `int` | `84` | 允许 PLL SC FBDIV 上限。 |
| `gate_reg_high_means_open` | `bool` | `false` | 为真时门控寄存器写 1 表示打开，**config_reg** 写入值与节点 **open** 一致；为假时写 1 表示关闭，按位取反后写入。节点 **open** 仍为仿真门开闭语义。 |
| `div_reg_high_means_reset` | `bool` | `false` | 为真时 div **rst** 写 1 表示复位、写 0 不复位；为假时写 0 表示复位、写 1 不复位。**config_reg** 在 **rst** 上先写复位电平再写不复位电平。 |
| `dto_reg_high_means_reset` | `bool` | `false` | 为真时 dto **rst** 写 1 表示复位、写 0 不复位；为假时写 0 表示复位、写 1 不复位。**config_reg** 在 **rst** 上先写复位电平再写不复位电平。 |
无法在优先区间内配准时仍写出寄存器，并 `uvm_error`。

### 寄存器路径

在 `settings` 中填写 `class_regmodel` 且节点配置了 `reg` 或 `regs` 时，下列路径写法生效：

`reg` 与 `regs` 的值为自寄存器模型顶层起的点分路径，可在末尾指定 field 内比特范围：

| 写法 | 含义 |
| --- | --- |
| `blk.field` | 整个 field；offset 为 0，width 为 field 位宽 |
| `blk.field[1]` | 仅 bit 1，位宽 1 |
| `blk.field[3:0]` | 从 lsb 0 起连续 4 位 |

**config_reg** 只更新所列比特，field 内其余位保持不变。

对 **req.nodes** 内节点按固定五段写寄存器，与同段内列表下标无关：全部 **pll** 写寄存器后统一 **wait_lock**；全部 **div** 与 **dto**；**open** 为真的 **gate**；全部 **mux**；**open** 为假的 **gate**。参考频率与输出 **frequence** 均与上次写入相同时，该 **pll** 跳过寄存器更新且不再 **wait_lock**。

### Tree

单棵时钟树的标识与节点集合。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `name` | `str` | 必填 | 时钟树名称。 |
| `nodes` | `dict[str, Node]` | 必填 | 本棵时钟树的节点表，键为节点 name，节点体内勿填 name。 |

### Node

所有节点都可以填写下列公共字段。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | 必填 | 节点类型。 |
| `name` | `str` | — | 由 `nodes` 字典键注入，配置中勿填。 |
| `path` | `str` | `""` | RTL 层次路径，用于 **tree_connection** 与 interface 展开；不写入节点类。留空则不生成 interface。 |
| `freq` | `optional int` | `null` | 典型频率。 |

| `kind` | 主要字段 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `source` | — | — | 时钟源节点，无 `source` 字段；下游由各节点 `source` 指回本节点名推导。 |
| `pll` | `source`, `pll_kind`, `regs` | `source`、`pll_kind` 必填 | PLL 节点；`source` 写参考时钟前级；**config_reg** 用前级 **frequence** 算分频，无前级句柄则 **uvm_fatal**；`pll_kind` 为 `tci`、`sc`、`dw` 之一，大小写不限；`regs` 为逻辑名到寄存器模型路径的映射，值可带比特范围后缀，非空时键须与该 `pll_kind` 允许集合完全一致。 |
| `clk` | `source` | `source` 必填 | 时钟输出节点，`source` 写前级节点名。 |
| `gate` | `source`, `reg` | `source` 必填 | 门控节点；`reg` 为可选寄存器模型点分路径，可带比特范围后缀。 |
| `div` | `source`, `regs` | `source` 必填 | 分频节点；`regs` 非空时键为 `rst`、`load`、`div`，值可带比特范围后缀。 |
| `dto` | `source`, `regs` | `source` 必填 | DTO 节点；`regs` 非空时键为 `rst`、`load`、`bypass`、`step`，值可带比特范围后缀。 |
| `inv` | `source` | `source` 必填 | 反相节点，`source` 写前级节点名。 |
| `mux` | `source`, `reg` | `source` 可省略或 `{}` | 多路选择节点；`source` 键为输入序号；有输入时 **cst_base** 约束 **sel inside**；`reg` 为可选寄存器模型点分路径，可带比特范围后缀。 |
