# clock_tree

![](images/data_tree_task.drawio.svg)

## 示例

```yaml
trees:
  - name: main
    nodes:
      osc:
        kind: source
        freq: 24000000
      pll0:
        kind: pll
        source: osc
        pll_kind: tci
        freq: 1000000000
      clk_cpu:
        kind: clk
        source: pll0
        freq: 1000000000
settings:
  class_prefix: chip_clk_
```

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `trees` | `list[Tree]` | | 时钟树。 |
| `settings` | `Settings` | | 全局选项。 |

### Settings

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `class_prefix` | `str` | `clk_tree_` | 命名前缀。 |
| `class_regmodel` | `str` | `""` | 寄存器模型类型名。 |
| `min_freq_hz` | `int` | `15000` | 测量接口与 check_measure 默认最低频率，单位 Hz。 |
| `max_freq_hz` | `int` | `5000000000` | **clk** 节点 randomize 后允许的最高频率，单位 Hz。 |
| `active_cycles` | `int` | `1` | 判定时钟有活动所需连续上升沿个数；超过一个最低频率周期仍无边沿则 inactive。 |
| `stable_cycles` | `int` | `3` | 活动确认后频率或占空比各自连续稳定所需周期数；中途失稳则重新计数。 |
| `mux_switch_wait_cycles` | `int` | `3` | **config_reg** 写 **mux** 选择前，按待切换 **mux** 最慢直接前级时钟等待的周期数。 |
| `period_tolerance` | `float` | `0.01` | 相邻周期相对偏差上限。 |
| `duty_min` | `float` | `50` | 允许占空比下限，百分数；闭区间端点计入合格。 |
| `duty_max` | `float` | `66` | 允许占空比上限，百分数；闭区间端点计入合格。 |
| `duty_tolerance_pct` | `float` | `0.05` | 占空比允许范围在 **duty_min**、**duty_max** 之外的容差，百分数点；合格区间为 **[duty_min − duty_tolerance_pct, duty_max + duty_tolerance_pct]**。 |
| `pll_lock_timeout_us` | `int` | `1000` | PLL lock 等待上限，微秒。 |
| `pll_sc_fbdiv_min` | `int` | `16` | 允许 PLL SC FBDIV 下限。 |
| `pll_sc_fbdiv_max` | `int` | `84` | 允许 PLL SC FBDIV 上限。 |
| `gate_reg_high_means_open` | `bool` | `false` | 为真时门控寄存器位 1 表示打开；为假时 1 表示关闭。 |
| `inv_reg_high_means_inverted` | `bool` | `false` | 为真时 inv 寄存器位 1 表示反相输出；为假时 1 表示直通。 |
| `div_reg_high_means_reset` | `bool` | `false` | 为真时 div **rst** 位 1 表示复位、0 不复位；为假时 0 表示复位、1 不复位。 |
| `dto_reg_high_means_reset` | `bool` | `false` | 为真时 dto **rst** 位 1 表示复位、0 不复位；为假时 0 表示复位、1 不复位。 |
| `should_reset_div` | `bool` | `false` | 为真时每次 **config_reg** 写 div 都先拉 **rst** 复位再释放；为假时首次只写 **rst** 不复位并写 **div** 与 **load**，此后仅更新 **div** 与 **load**。 |
| `should_reset_dto` | `bool` | `false` | 为真时每次 **config_reg** 写 dto 都先拉 **rst** 复位再释放；为假时首次只写 **rst** 不复位并写 **step**、**load** 与 **bypass**，此后仅更新这三项。 |

### 配置值写法

#### 寄存器模型路径

寄存器路径按 `.` 分隔，可指定比特范围。

| 写法 | 含义 |
| --- | --- |
| `blk.field` | 整个 field |
| `blk.field[1]` | 仅 bit 1 |
| `blk.field[3:0]` | 从 bit 0 起连续 4 位 |

#### 前级引用

写 **nodes** 中的节点名；多路输出加 `[输出名]`，方括号内为字符串，与 **output_groups** 或 **regs** 内 `postdiv1[名字]` 一致。

| 写法 | 含义 |
| --- | --- |
| `osc` | 通常写法，单路输出前级 |
| `pll0` | 单路输出前级 |
| `pll0["0"]` 或 `pll0[0]` | 多路输出前级，输出名为 `0` |

### Tree

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `name` | `str` | | 时钟树名称。 |
| `module_path` | `str` | `""` | 该树可测量 RTL 模块的层次路径，按 `.` 分隔；非空时仅 **path** 等于此路径或以其为前缀的节点接测量 interface 并参与 **check_measure**；省略或空字符串表示不按模块过滤。 |
| `nodes` | `dict[str, Node]` | | 节点表，键为节点名。 |

### Node - source

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `source` | |
| `source_kind` | `str` | `source` | 取 `source`、`pad`。 |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `freq` | `int` | | 典型频率，单位 Hz。 |

**source_kind** 为 `pad` 时字段与上表相同，仅型号不同。

### Node - pll

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `pll` | |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `freq` | `int` | | 典型频率，单位 Hz。 |
| `source` | `str` | | 参考时钟前级引用；省略或空表示无前级。 |
| `pll_kind` | `str` | | 取 `tci`、`sc`、`dw`、`inno`。`inno` 固定两路输出。 |

#### tci

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `regs.lock` | `str` | | PLL lock 状态位。 |
| `regs.bypass` | `str` | | bypass 开关。 |
| `regs.pwrdn` | `str` | | 掉电控制。 |
| `regs.reset` | `str` | | 复位控制。 |
| `regs.clkod` | `str` | | 输出分频系数。 |
| `regs.clkf` | `str` | | 反馈倍频系数。 |
| `regs.clkr` | `str` | | 参考分频系数。 |
| `regs.bwadj` | `str` | | 环路带宽调节。 |

#### sc

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `regs.lock` | `str` | | PLL lock 状态位。 |
| `regs.vocpd` | `str` | | VCO 掉电。 |
| `regs.postdivpd` | `str` | | 后级分频掉电。 |
| `regs.dsmpd` | `str` | | ΔΣ 调制掉电。 |
| `regs.pd` | `str` | | 掉电控制。 |
| `regs.bypass` | `str` | | bypass 开关。 |
| `regs.refdiv` | `str` | | 参考分频系数。 |
| `regs.postdiv2` | `str` | | 后级分频 2 系数。 |
| `regs.postdiv1` | `str` | | 后级分频 1 系数。 |
| `regs.fbdiv` | `str` | | 反馈分频系数。 |

#### dw

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `regs.lock` | `str` | | PLL lock 状态位。 |
| `regs.fbdiv` | `str` | | 反馈分频系数。 |
| `regs.prediv` | `str` | | 前级分频系数。 |
| `regs.reset` | `str` | | 复位控制。 |
| `regs.pwron` | `str` | | 上电控制。 |
| `regs.shift` | `str` | | 频点偏移。 |
| `regs.bypass` | `str` | | bypass 开关。 |
| `regs.divvcor` | `str` | | VCO 分频系数。 |
| `regs.r` | `str` | | R 分频系数。 |
| `regs.p` | `str` | | P 分频系数。 |
| `regs.divvcop` | `str` | | VCO 后级分频系数。 |
| `regs.enr` | `str` | | R 通道使能。 |
| `regs.enp` | `str` | | P 通道使能。 |

#### inno

固定两路输出，组内共用 **lock**、**pd**、**refdiv**、**fbdiv**，每路各有 **postdiv1**、**postdiv2**。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `regs.lock` | `str` | | PLL lock 状态位。 |
| `regs.pd` | `str` | | 掉电控制。 |
| `regs.refdiv` | `str` | | 参考分频系数。 |
| `regs.fbdiv` | `str` | | 反馈分频系数。 |
| `regs.postdiv1[0]` | `str` | | 第 0 路后级分频 1 系数。 |
| `regs.postdiv2[0]` | `str` | | 第 0 路后级分频 2 系数。 |
| `regs.postdiv1[1]` | `str` | | 第 1 路后级分频 1 系数。 |
| `regs.postdiv2[1]` | `str` | | 第 1 路后级分频 2 系数。 |

### Node - clk

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `clk` | |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `freq` | `int` | | 典型频率，单位 Hz；省略则频率与使能均不参与随机；正数同时指定频率与使能；负值仅放宽输出频率随机范围。 |
| `source` | `str` | | 前级引用；省略或空表示无前级。 |
| `always_active` | `bool` | `false` | 为真时表示时钟始终使能：**low_power** 不关断，**test_route** 不参与探测；频率可随上游变化，trees 不锁定 **frequence**。 |

### Node - gate

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `gate` | |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `source` | `str` | | 前级引用；省略或空表示无前级。 |
| `open` | `int` | | 门控开关；0 关闭、1 打开；省略则参与随机化。 |
| `reg` | `str` | `""` | 门控寄存器模型路径。 |

### Node - cell

直通单元，输出频率与活动状态与前级相同；各 **cell_kind** 共用同一仿真类。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `cell` | |
| `cell_kind` | `str` | `cell` | 任意非空字符串，仅作配置记录。 |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `source` | `str` | | 前级引用；省略或空表示无前级。 |

### Node - div

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `div` | |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `source` | `str` | | 前级引用；省略或空表示无前级。 |
| `regs.rst` | `str` | | 复位位。 |
| `regs.load` | `str` | | 加载位。 |
| `regs.div` | `str` | | 分频系数。 |

### Node - div_r

固定分频，无寄存器；配置 **ratio** 后仿真分频比恒为该值。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `div_r` | 等价于 `kind: div` 且 `div_kind: div_r`。 |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `source` | `str` | | 前级引用；省略或空表示无前级。 |
| `ratio` | `int` | | 固定分频比，大于 0；不受可配置 **div** 的 64 上限。 |

### Node - dto

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `dto` | |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `source` | `str` | | 前级引用；省略或空表示无前级。 |
| `regs.rst` | `str` | | 复位位。 |
| `regs.load` | `str` | | 加载位。 |
| `regs.bypass` | `str` | | bypass 位。 |
| `regs.step` | `str` | | 步进控制。 |

### Node - inv

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `inv` | |
| `inv_kind` | `str` | `inv` | 取 `inv`、`inv_mux`、`inv_cell`；`inv_cell` 与 `inv` 仿真行为相同。 |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `source` | `str` | | 前级引用；省略或空表示无前级。 |
| `reg` | `str` | `""` | 反相/直通控制寄存器模型路径。 |

### Node - mux

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `mux` | |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `source` | `dict[str, str]` | `{}` | 输入标签到前级引用的映射。 |
| `reg` | `str` | `""` | 选择寄存器模型路径。 |
