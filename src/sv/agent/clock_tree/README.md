# clock_tree

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
| `min_freq_hz` | `int` | `500` | 测量接口与 check_freq 默认最低频率，单位 Hz。 |
| `stable_cycles` | `int` | `3` | 连续稳定所需周期数。 |
| `period_tolerance` | `float` | `0.05` | 相邻周期相对偏差上限。 |
| `duty_min` | `float` | `33` | 允许占空比下限，百分数；闭区间端点计入合格。 |
| `duty_max` | `float` | `66` | 允许占空比上限，百分数；闭区间端点计入合格。 |
| `pll_lock_timeout_us` | `int` | `1000` | PLL lock 等待上限，微秒。 |
| `pll_sc_fbdiv_min` | `int` | `16` | 允许 PLL SC FBDIV 下限。 |
| `pll_sc_fbdiv_max` | `int` | `84` | 允许 PLL SC FBDIV 上限。 |
| `gate_reg_high_means_open` | `bool` | `false` | 为真时门控寄存器位 1 表示打开；为假时 1 表示关闭。 |
| `div_reg_high_means_reset` | `bool` | `false` | 为真时 div **rst** 位 1 表示复位、0 不复位；为假时 0 表示复位、1 不复位。 |
| `dto_reg_high_means_reset` | `bool` | `false` | 为真时 dto **rst** 位 1 表示复位、0 不复位；为假时 0 表示复位、1 不复位。 |
| `should_reset_div` | `bool` | `false` | 为真时 **config_reg** 首次配置 div 先拉 **rst** 复位再释放；为假时首次只把 **rst** 写不复位并写 **div** 与 **load**。 |
| `should_reset_dto` | `bool` | `false` | 为真时 **config_reg** 首次配置 dto 先拉 **rst** 复位再释放；为假时首次只把 **rst** 写不复位并写 **step**、**load** 与 **bypass**。 |

### 配置值写法

#### 寄存器模型路径

寄存器路径按 `.` 分隔，可指定比特范围。

| 写法 | 含义 |
| --- | --- |
| `blk.field` | 整个 field |
| `blk.field[1]` | 仅 bit 1 |
| `blk.field[3:0]` | 从 bit 0 起连续 4 位 |

#### 前级引用

写 **nodes** 中的节点名；多路输出加 `[序号]`。

| 写法 | 含义 |
| --- | --- |
| `osc` | 通常写法，单路输出前级 |
| `pll0` | 单路输出前级 |
| `pll0[0]` | 多路输出前级，第 0 路 |
| `pll0[1]` | 多路输出前级，第 1 路 |

### Tree

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `name` | `str` | | 时钟树名称。 |
| `nodes` | `dict[str, Node]` | | 节点表，键为节点名。 |

### Node - source

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `source` | |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `freq` | `int` | | 典型频率，单位 Hz。 |

### Node - pll

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `pll` | |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `freq` | `int` | | 典型频率，单位 Hz。 |
| `source` | `str` | | 参考时钟前级引用。 |
| `pll_kind` | `str` | | 取 `tci`、`sc`、`dw`、`inno`。 |
| `output_count` | `int` | `1` | 有几路输出。仅 `inno` 可用。 |

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

**output_count** 为 1：

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `regs.lock` | `str` | | PLL lock 状态位。 |
| `regs.pd` | `str` | | 掉电控制。 |
| `regs.refdiv` | `str` | | 参考分频系数。 |
| `regs.fbdiv` | `str` | | 反馈分频系数。 |
| `regs.postdiv1` | `str` | | 后级分频 1 系数。 |
| `regs.postdiv2` | `str` | | 后级分频 2 系数。 |

**output_count** 大于 1：

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

更多输出路时 **regs** 内名字序号递增，如 `postdiv1[2]`、`postdiv2[2]`。

### Node - clk

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `clk` | |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `freq` | `int` | | 典型频率，单位 Hz。 |
| `source` | `str` | | 前级引用。 |

### Node - gate

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `gate` | |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `source` | `str` | | 前级引用。 |
| `reg` | `str` | `""` | 门控寄存器模型路径。 |

### Node - div

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `div` | |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `source` | `str` | | 前级引用。 |
| `regs.rst` | `str` | | 复位位。 |
| `regs.load` | `str` | | 加载位。 |
| `regs.div` | `str` | | 分频系数。 |

### Node - dto

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `dto` | |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `source` | `str` | | 前级引用。 |
| `regs.rst` | `str` | | 复位位。 |
| `regs.load` | `str` | | 加载位。 |
| `regs.bypass` | `str` | | bypass 位。 |
| `regs.step` | `str` | | 步进控制。 |

### Node - inv

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `inv` | |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `source` | `str` | | 前级引用。 |

### Node - mux

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `mux` | |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `source` | `dict[str, str]` | `{}` | 输入标签到前级引用的映射。 |
| `reg` | `str` | `""` | 选择寄存器模型路径。 |
