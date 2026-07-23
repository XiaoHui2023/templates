# clock_tree

![](images/data_tree_task.drawio.svg)

## 示例

```yaml
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

纯路径探针可使用 `settings.probe_mode: true`。该模式不表达树状连接关系，只检查带 `path` 且有正数 `freq` 的 `clk/cell`，以及 `active: false` 的 `clk/cell`；`source`、`pll` 和中间节点不会出现在生成的 `tree_interface.sv` 中。

```yaml
nodes:
  osc:
    kind: source
  clk_cpu:
    kind: clk
    path: dut.clk_cpu
    freq: 1000000000
settings:
  probe_mode: true
```

纯 model 寄存器配置可使用 `settings.direct_config: true`。该模式额外生成 `model/model.f` 与 `model/direct_config.sv`；`all.f` 仍为正常 agent filelist。配置入口为 `<class_prefix>config_reg(tree)`，用于不接 agent、只用 model 完成寄存器配置的场景。

## Agent 使用

完整 agent 模式会编译 model、core、sequence、component 与 top 文件。平台中创建 `agent` 与 `tree`，调用 `tree.build(regmodel)` 绑定寄存器并随机化；如果配置中有 `clk.path` 或 `cell.path`，还要在顶层例化 `tree_interface`，再调用 `<class_prefix>connect(tree, tree_if)` 连接测量接口。

```systemverilog
<class_prefix>agent clk_agt;
<class_prefix>kit_sequencer clk_sqr;
<class_prefix>tree tree;

function void build_phase(uvm_phase phase);
    clk_agt = <class_prefix>agent::type_id::create("clk_agt", this);
    tree = <class_prefix>tree::type_id::create("tree");
    tree.build(your_regmodel);
    <class_prefix>connect(tree, your_top_module.clk_tree_if);
    $cast(clk_sqr, clk_agt.sqr);
    uvm_config_db#(<class_prefix>tree)::set(this, "clk_agt", "tree", tree);
endfunction
```

常用入口在 kit sequencer 上：只配置寄存器用 `clk_sqr.config_reg()`，只测量用 `clk_sqr.check_measure()`，配置后测量用 `clk_sqr.test_measure()`；低功耗或改频等配置先改 `tree` 中节点属性，再调用 `config_reg()` 应用。

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `nodes` | `dict[str, Node]` | | 节点表，键为节点名。 |
| `settings` | `Settings` | | 全局选项。 |

### Settings

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `class_prefix` | `str` | `clk_tree_` | 命名前缀。 |
| `class_regmodel` | `str` | `""` | 寄存器模型类型名。 |
| `probe_mode` | `bool` | `false` | 为真时启用纯路径探针模式：不连接前级，只检查带 **path** 且有正数 **freq** 的 **clk/cell**，以及 **active** 为假的 **clk/cell**。 |
| `direct_config` | `bool` | `false` | 为真时只生成 model 目录文件和直接寄存器配置入口。 |
| `min_freq_hz` | `int` | `15000` | 测量接口与 check_measure 默认最低频率，单位 Hz。 |
| `max_freq_hz` | `int` | `5000000000` | **clk/cell** 节点 randomize 后允许的最高频率，单位 Hz。 |
| `active_cycles` | `int` | `1` | 判定时钟有活动所需连续上升沿个数；超过一个最低频率周期仍无边沿则 inactive。 |
| `stable_cycles` | `int` | `3` | 活动确认后频率或占空比各自连续稳定所需周期数；中途失稳则重新计数。 |
| `mux_switch_wait_cycles` | `int` | `3` | **config_reg** 写 **mux** 选择前，按待切换 **mux** 最慢直接前级时钟等待的周期数。 |
| `period_tolerance` | `float` | `0.02` | 相邻周期相对偏差上限。 |
| `div_freq_tolerance` | `float` | `0.01` | 分频器解析频率相对容差。 |
| `duty_min` | `float` | `48` | 允许占空比下限，百分数；闭区间端点计入合格。 |
| `duty_max` | `float` | `67` | 允许占空比上限，百分数；闭区间端点计入合格。 |
| `duty_tolerance_pct` | `float` | `0.05` | 占空比允许范围在 **duty_min**、**duty_max** 之外的容差，百分数点；合格区间为 **[duty_min − duty_tolerance_pct, duty_max + duty_tolerance_pct]**。 |
| `pll_lock_timeout_us` | `int` | `100` | PLL lock 等待上限，微秒。 |
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

### Nodes

**nodes** 是顶层字段，键为节点名；节点值不可为 **null**。

所有节点都支持公共字段 **present**，默认 **true**。写 **present: false** 时，该节点不生成 SV 对象、不进入 tree；其它节点引用它作为 **source** 时不连接。

### Node - source

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `source` | |
| `source_kind` | `str` | `source` | 取 `source`、`pad`。 |
| `freq` | `int` | | 典型频率，单位 Hz；非 `probe_mode` 必填，`probe_mode` 可省略且不参与检查。 |

**source_kind** 为 `pad` 时字段与上表相同，仅型号不同。

### Node - pll

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `pll` | |
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
| `path` | `str` | | RTL 层次路径，按 `.` 分隔；**present** 为真时必填。 |
| `freq` | `int` | | 典型频率，单位 Hz；省略则频率与使能均不参与随机；正数同时指定频率与使能；负值仅放宽输出频率随机范围。 |
| `active` | `bool` | `true` | 期望运行态是否有时钟；为假时仍生成 SV 对象并检查 inactive。 |
| `source` | `str` | | 前级引用；省略或空表示无前级。 |
| `stable` | `bool` | `false` | 锚定时钟：结构探测与低功耗下不得关断或改频。为真时应给出正整数 **freq**，tree 锁定 **frequence** 与 **enabled**。**low_power** 不关断该 **clk**。**test_route** 跳过该节点及其当前选通路径上的 **gate**、**mux**、**div**、**pll** 探测，并固定路径控制量；路径上 **pll** 不参与改频策略。**check_measure** 期望为锁定后的 **_resolved_freq**。 |
| `volatile` | `bool` | `false` | 独立测量时钟；source 正常连接并参与频率推算，只参与 `check_measure`，不参与 `test_route`、`test_flip` 或 stable 路径锚定；`low_power` 会关闭该时钟；`check_measure` 中只检查频率。 |

### Node - gate

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `gate` | |
| `source` | `str` | | 前级引用；省略或空表示无前级。 |
| `open` | `int` | | 门控开关；0 关闭、1 打开；省略则参与随机化。 |
| `reg` | `str` | `""` | 门控寄存器模型路径。 |

### Node - cell

直通单元，未指定时输出频率与活动状态与前级相同；各 **cell_kind** 共用同一仿真类。`check_measure` 只检查频率。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `cell` | |
| `path` | `str` | | RTL 层次路径，按 `.` 分隔；**present** 为真时必填。 |
| `cell_kind` | `str` | `cell` | 任意非空字符串，仅作配置记录。 |
| `freq` | `int` | | 典型频率，单位 Hz；省略则不指定频率。 |
| `active` | `bool` | | 期望运行态是否有时钟；省略则不指定活动状态；为 `false` 时表示关闭。 |
| `source` | `str` | | 前级引用；省略或空表示无前级。 |

### Node - div

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `div` | |
| `source` | `str` | | 前级引用；省略或空表示无前级。 |
| `regs.rst` | `str` | | 复位位。 |
| `regs.load` | `str` | | 加载位。 |
| `regs.div` | `str` | | 分频系数。 |

### Node - div_r

固定分频，无寄存器；配置 **ratio** 后仿真分频比恒为该值。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `div_r` | 等价于 `kind: div` 且 `div_kind: div_r`。 |
| `source` | `str` | | 前级引用；省略或空表示无前级。 |
| `ratio` | `int` | | 固定分频比，大于 0；不受可配置 **div** 的 64 上限。 |

### Node - dto

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `dto` | |
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
| `source` | `str` | | 前级引用；省略或空表示无前级。 |
| `reg` | `str` | `""` | 反相/直通控制寄存器模型路径。 |

### Node - mux

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `mux` | |
| `source` | `dict[str, str]` | `{}` | 输入标签到前级引用的映射。 |
| `reg` | `str` | `""` | 选择寄存器模型路径。 |
