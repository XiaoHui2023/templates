# pll_mini

![](images/pipeline.drawio.svg)

## 示例

```yaml
ralf: example.ralf
tree:
  name: main
  nodes:
    xtal:
      kind: source
      freq: 24000000
    pll_sc:
      kind: pll
      source: xtal
      pll_kind: sc
      freq: 60000000
      regs:
        lock: blk_pll_sc.stat.lock
        fbdiv: blk_pll_sc.div.fbdiv
    clk_out:
      kind: clk
      source: pll_sc
      freq: 60000000
settings:
  main_fn: chip_pll_config
```

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `ralf` | `str` | | RALF 文件路径。 |
| `ralf_include_dirs` | `list[str]` | `[]` | RALF 引用其它文件时的额外搜索目录。 |
| `tree` | `Tree` | | 单棵时钟树。 |
| `settings` | `Settings` | 见下表 | 全局选项。 |

### Settings

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `main_fn` | `str` | `pll_mini_config` | 配置入口 C 函数名。 |
| `header_guard` | `str` | `PLL_MINI_H` | 头文件 include guard。 |
| `source_guard` | `str` | `PLL_MINI_C` | 源文件 include guard，避免被多次 include。 |
| `gate_reg_high_means_open` | `bool` | `false` | 门控寄存器写 1 是否表示打开。 |
| `div_reg_high_means_reset` | `bool` | `false` | div 的 rst 写 1 是否表示复位。 |
| `dto_reg_high_means_reset` | `bool` | `false` | dto 的 rst 写 1 是否表示复位。 |
| `pll_sc_fbdiv_min` | `int` | `16` | 允许 PLL SC FBDIV 下限。 |
| `pll_sc_fbdiv_max` | `int` | `84` | 允许 PLL SC FBDIV 上限。 |
| `consolver_timeout_ms` | `int` | | consolver 求解超时，毫秒。 |
| `reg_base_offset` | `int` | `0` | 寄存器整体偏移地址。 |

### 寄存器模型路径

寄存器路径按 `.` 分隔，可指定比特范围。

| 写法 | 含义 |
| --- | --- |
| `blk.field` | 整个 field |
| `blk.field[1]` | 仅 bit 1 |
| `blk.field[3:0]` | 从 bit 0 起连续 4 位 |

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
| `name` | `str` | | 时钟树名。 |
| `nodes` | `dict[str, Node]` | | 节点表，键为节点名。 |

### Node - source

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `source` | |
| `freq` | `int` | | 典型频率，单位 Hz。 |

### Node - pll

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `pll` | |
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
| `regs.postdiv1` | `str` | | 第 0 路后级分频 1 系数。 |
| `regs.postdiv2` | `str` | | 第 0 路后级分频 2 系数。 |
| `regs.postdiv1_1` | `str` | | 第 1 路后级分频 1 系数。 |
| `regs.postdiv2_1` | `str` | | 第 1 路后级分频 2 系数。 |

更多输出路时 **regs** 内名字序号递增，如 `postdiv1_2`、`postdiv2_2`。

### Node - clk

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `clk` | |
| `freq` | `int` | | 典型频率，单位 Hz。 |
| `source` | `str` | | 前级引用。 |

### Node - gate

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `gate` | |
| `source` | `str` | | 前级引用。 |
| `reg` | `str` | `""` | 门控寄存器模型路径。 |

### Node - div

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `div` | |
| `source` | `str` | | 前级引用。 |
| `regs.rst` | `str` | | 复位位。 |
| `regs.load` | `str` | | 加载位。 |
| `regs.div` | `str` | | 分频系数。 |

### Node - dto

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `dto` | |
| `source` | `str` | | 前级引用。 |
| `regs.rst` | `str` | | 复位位。 |
| `regs.load` | `str` | | 加载位。 |
| `regs.bypass` | `str` | | bypass 位。 |
| `regs.step` | `str` | | 步进控制。 |

### Node - inv

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `inv` | |
| `source` | `str` | | 前级引用。 |

### Node - mux

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `mux` | |
| `source` | `dict[str, str]` | `{}` | 输入标签到前级引用的映射。 |
| `reg` | `str` | `""` | 选择寄存器模型路径。 |
