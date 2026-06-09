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
| `trees` | `list[Tree]` | | 时钟树。 |
| `settings` | `Settings` | | 全局选项。 |

### Settings

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `class_prefix` | `str` | `clk_tree_` | 命名前缀。 |
| `class_regmodel` | `str` | `""` | 寄存器模型类型名。 |
| `min_freq_hz` | `int` | `500` | 仍活动的最低频率，单位 Hz。 |
| `stable_cycles` | `int` | `3` | 连续稳定所需周期数。 |
| `period_tolerance` | `float` | `0.05` | 相邻周期相对偏差上限。 |
| `duty_min` | `float` | `0.50` | 允许占空比下限。 |
| `duty_max` | `float` | `0.66` | 允许占空比上限。 |
| `pll_lock_timeout_us` | `int` | `1000` | PLL lock 等待上限，微秒。 |
| `pll_sc_fbdiv_min` | `int` | `16` | 允许 PLL SC FBDIV 下限。 |
| `pll_sc_fbdiv_max` | `int` | `84` | 允许 PLL SC FBDIV 上限。 |
| `gate_reg_high_means_open` | `bool` | `false` | 为真时门控寄存器位 1 表示打开；为假时 1 表示关闭。 |
| `div_reg_high_means_reset` | `bool` | `false` | 为真时 div **rst** 位 1 表示复位、0 不复位；为假时 0 表示复位、1 不复位。 |
| `dto_reg_high_means_reset` | `bool` | `false` | 为真时 dto **rst** 位 1 表示复位、0 不复位；为假时 0 表示复位、1 不复位。 |

### 寄存器模型路径

寄存器路径按 `.` 分隔，可指定比特范围。

| 写法 | 含义 |
| --- | --- |
| `blk.field` | 整个 field |
| `blk.field[1]` | 仅 bit 1 |
| `blk.field[3:0]` | 从 bit 0 起连续 4 位 |

- **gate**
- **mux**
- **pll**
  - **tci**
    - `lock`：PLL lock 状态位
    - `bypass`：bypass 开关
    - `pwrdn`：掉电控制
    - `reset`：复位控制
    - `clkod`：输出分频系数
    - `clkf`：反馈倍频系数
    - `clkr`：参考分频系数
    - `bwadj`：环路带宽调节
  - **sc**
    - `lock`：PLL lock 状态位
    - `vocpd`：VCO 掉电
    - `postdivpd`：后级分频掉电
    - `dsmpd`：ΔΣ 调制掉电
    - `pd`：掉电控制
    - `bypass`：bypass 开关
    - `refdiv`：参考分频系数
    - `postdiv2`：后级分频 2 系数
    - `postdiv1`：后级分频 1 系数
    - `fbdiv`：反馈分频系数
  - **dw**
    - `lock`：PLL lock 状态位
    - `fbdiv`：反馈分频系数
    - `prediv`：前级分频系数
    - `reset`：复位控制
    - `pwron`：上电控制
    - `shift`：频点偏移
    - `bypass`：bypass 开关
    - `divvcor`：VCO 分频系数
    - `r`：R 分频系数
    - `p`：P 分频系数
    - `divvcop`：VCO 后级分频系数
    - `enr`：R 通道使能
    - `enp`：P 通道使能
  - **inno**（**output_count** 为 1）
    - `lock`：PLL lock 状态位
    - `pd`：掉电控制
    - `refdiv`：参考分频系数
    - `fbdiv`：反馈分频系数
    - `postdiv1`：后级分频 1 系数
    - `postdiv2`：后级分频 2 系数
  - **inno**（**output_count** 大于 1）
    - `lock`：PLL lock 状态位
    - `pd`：掉电控制
    - `refdiv`：参考分频系数
    - `fbdiv`：反馈分频系数
    - `postdiv1[0]`：第 0 路后级分频 1 系数
    - `postdiv2[0]`：第 0 路后级分频 2 系数
    - `postdiv1[1]`：第 1 路后级分频 1 系数
    - `postdiv2[1]`：第 1 路后级分频 2 系数
    - 更多输出路时序号递增，如 `postdiv1[2]`、`postdiv2[2]`
- **div**
  - `rst`：复位位
  - `load`：加载位
  - `div`：分频系数
- **dto**
  - `rst`：复位位
  - `load`：加载位
  - `bypass`：bypass 位
  - `step`：步进控制

### 前级引用

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

### Node

#### 公共字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | | 节点类型。 |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `freq` | `optional int` | | 典型频率，单位 Hz。 |

#### source

除公共字段外无额外键。

#### pll

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `source` | `str` | | 参考时钟前级引用。 |
| `pll_kind` | `str` | | 取 `tci`、`sc`、`dw`、`inno`。 |
| `output_count` | `int` | `1` | 有几路输出。仅 `inno` 可用。 |
| `regs` | `dict[str, str]` | `{}` | 寄存器模型路径。 |

#### clk

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `source` | `str` | | 前级引用。 |

#### gate

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `source` | `str` | | 前级引用。 |
| `reg` | `str` | `""` | 寄存器模型路径。 |

#### div

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `source` | `str` | | 前级引用。 |
| `regs` | `dict[str, str]` | `{}` | 寄存器模型路径。 |

#### dto

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `source` | `str` | | 前级引用。 |
| `regs` | `dict[str, str]` | `{}` | 寄存器模型路径。 |

#### inv

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `source` | `str` | | 前级引用。 |

#### mux

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `source` | `dict[str, str]` | `{}` | 输入标签到前级引用的映射。 |
| `reg` | `str` | `""` | 寄存器模型路径。 |
