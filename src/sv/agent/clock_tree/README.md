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

### Settings

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `class_prefix` | `str` | `clk_tree_` | 命名前缀。 |
| `class_regmodel` | `str` | 空 | 寄存器模型类型名。 |
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

节点 **reg**、**regs** 的值为寄存器模型路径，按 `.` 分隔，首段为顶层块名；可在末尾指定 field 内比特范围：

| 写法 | 含义 |
| --- | --- |
| `blk.field` | 整个 field |
| `blk.field[1]` | 仅 bit 1 |
| `blk.field[3:0]` | 从 bit 0 起连续 4 位 |

### 前级引用

节点 **source** 与 **mux** 的 **source** 映射值，写 **nodes** 字典中的节点名字；多路输出时在方括号内写输出序号：

| 写法 | 含义 |
| --- | --- |
| `pll0` | 取该节点第 0 路输出 |
| `pll0[1]` | 取第 1 路输出 |

**mux** 的 **source** 为字典：键为输入标签，值为上表字符串。

### Tree

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `name` | `str` | 必填 | 时钟树名称。 |
| `nodes` | `dict[str, Node]` | 必填 | 节点表，键为节点名。 |

### Node

`kind` 选定下列之一；各节点另含 **公共字段** 与对应 **kind** 字段。

#### 公共字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | 必填 | 节点类型。 |
| `path` | `str` | `""` | RTL 层次路径，按 `.` 分隔。 |
| `freq` | `optional int` | `null` | 典型频率，单位 Hz。 |

#### source

除公共字段外无额外键；`kind` 为 `source`。

#### pll

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `source` | `str` | 必填 | 参考时钟前级引用。 |
| `pll_kind` | `str` | 必填 | 取 `tci`、`sc`、`dw`、`inno`。 |
| `output_count` | `int` | `1` | 输出路数；大于 1 时 `pll_kind` 须为 `inno`。 |
| `regs` | `dict[str, str]` | `{}` | 逻辑名到寄存器模型路径的映射；非空时键须与 `pll_kind`、`output_count` 允许集合一致。 |

#### clk

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `source` | `str` | 必填 | 前级引用。 |

#### gate

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `source` | `str` | 必填 | 前级引用。 |
| `reg` | `str` | `""` | 寄存器模型路径。 |

#### div

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `source` | `str` | 必填 | 前级引用。 |
| `regs` | `dict[str, str]` | `{}` | 非空时键为 `rst`、`load`、`div`，值为寄存器模型路径。 |

#### dto

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `source` | `str` | 必填 | 前级引用。 |
| `regs` | `dict[str, str]` | `{}` | 非空时键为 `rst`、`load`、`bypass`、`step`，值为寄存器模型路径。 |

#### inv

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `source` | `str` | 必填 | 前级引用。 |

#### mux

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `source` | `dict[str, str]` | `{}` | 输入标签到前级引用的映射。 |
| `reg` | `str` | `""` | 寄存器模型路径。 |
