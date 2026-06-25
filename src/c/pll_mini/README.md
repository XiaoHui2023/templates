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
| `period_tolerance` | `float` | `0.01` | 分频求解相对频率容差。 |
| `reg_base_offset` | `int` | `0` | 寄存器整体偏移地址。 |

### 寄存器模型路径

寄存器路径按 `.` 分隔，可指定比特范围。

| 写法 | 含义 |
| --- | --- |
| `blk.field` | 整个 field |
| `blk.field[1]` | 仅 bit 1 |
| `blk.field[3:0]` | 从 bit 0 起连续 4 位 |

### 前级引用

写 **nodes** 中的节点名；多路输出加 `[输出名]`。

| 写法 | 含义 |
| --- | --- |
| `osc` | 通常写法，单路输出前级 |
| `pll0` | 单路输出前级 |
| `pll_inno[0]` | 多路输出前级，输出名为 `0` |
| `cpu_gate0[hclk]` | cpu_gate 多路输出前级 |

### Tree

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `name` | `str` | | 时钟树名。 |
| `nodes` | `dict[str, Node]` | | 节点表，键为节点名。 |

### Node - source

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `source` | |
| `source_kind` | `str` | `source` | 取 `source`、`pad`、`vdd`、`gnd`。 |
| `freq` | `int` | | 典型频率，单位 Hz；`vdd`、`gnd` 为 0 或省略。 |

### Node - pll

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `pll` | |
| `freq` | `int` | | 典型频率，单位 Hz。 |
| `source` | `str` | | 参考时钟前级引用。 |
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
| `freq` | `int` | | 典型频率，单位 Hz；省略表示不指定频率约束。 |
| `source` | `str` | | 前级引用。 |
| `always_active` | `bool` | `false` | 为真时全程保持有效。 |

### Node - gate

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `gate` | |
| `source` | `str` | | 前级引用。 |
| `reg` | `str` | `""` | 门控寄存器模型路径。 |

### Node - div

`kind` 为 `div`，用 `div_kind` 区分型号。旧写法 `kind: dto` 等会在载入时归并为 `kind: div`。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `div` | |
| `div_kind` | `str` | `div` | 取 `div`、`div_n`、`dto`、`dto_n`、`cpu_gate`、`div_r`。 |
| `source` | `str` | | 前级引用。 |
| `ratio` | `int` | | `div_r` 必填固定分频比 1～64；`cpu_gate` 可填 2、3、4、6；其它 **div_kind** 可填以固定分频比。 |
| `regs` | `dict` | `{}` | 键由 `div_kind` 决定；`div_r` 须为空。 |

**div_kind** 为 `div` 或 `div_n`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `regs.rst` | `str` | 复位位。 |
| `regs.load` | `str` | 加载位。 |
| `regs.div` | `str` | 分频系数。 |

**div_kind** 为 `dto` 或 `dto_n`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `regs.rst` | `str` | 复位位。 |
| `regs.load` | `str` | 加载位。 |
| `regs.bypass` | `str` | bypass 位。 |
| `regs.step` | `str` | 步进控制。 |

**div_kind** 为 `cpu_gate` 时，固定 3 路输出：

| 输出名 | 频率行为 |
| --- | --- |
| `hclk_en` | 按分频比输出 |
| `hclk` | 按分频比输出 |
| `clk_arm_core` | 与前级同频 |

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `regs.rst` | `str` | 复位位。 |
| `regs.div` | `str` | 4 bit 分频 field，比只能是 2、3、4、6。 |

前级引用应写 `节点名[输出名]`。

### Node - inv

反相器仅作频率透传，**不写寄存器**，生成代码跳过配置。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `inv` | |
| `inv_kind` | `str` | `inv` | 取 `inv`、`inv_mux`、`inv_cell`。 |
| `source` | `str` | | 前级引用。 |

### Node - mux

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `mux` | |
| `source` | `dict[str, str]` | `{}` | 输入标签到前级引用的映射。 |
| `sel` | `int` | | mux 选择值；省略表示由求解器决定。 |
| `reg` | `str` | `""` | 选择寄存器模型路径。 |

### Node - cell

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `cell` | |
| `cell_kind` | `str` | `cell` | 任意非空字符串，仅作配置记录。 |
| `source` | `str` | | 前级引用。 |
