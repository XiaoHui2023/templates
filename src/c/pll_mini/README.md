# pll_mini

## 示例

```yaml
ralf: example/normal.ralf
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
      vocpd: blk_pll_sc.pd.vocpd
      postdivpd: blk_pll_sc.pd.postdivpd
      dsmpd: blk_pll_sc.pd.dsmpd
      pd: blk_pll_sc.pd.pd
      bypass: blk_pll_sc.pd.bypass
      refdiv: blk_pll_sc.div.refdiv
      postdiv2: blk_pll_sc.div.postdiv2
      postdiv1: blk_pll_sc.div.postdiv1
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
| `nodes` | `dict[str, Node]` | | 节点表，键为节点名。 |
| `extra_regs` | `list[ExtraRegEntry]` | `[]` | 附加寄存器字段。 |
| `settings` | `Settings` | `{}` | 全局选项。 |

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
| `solve_timeout_ms` | `int` | | 定向搜索求解超时，毫秒。 |
| `debug_consolver_smt_path` | `str` | | 调试用 SMT-LIB 输出路径；相对路径按输入 YAML 所在目录解析。 |
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
| `pll_inno[0]` | 多路输出前级，输出名为 `0` |

### Nodes

类型直接使用插件名：`source`、`source_pad`、`pll_tci`、`pll_sc`、`pll_dw`、`pll_inno`、`div_div`、`div_dto`、`div_div_r`、`inv`、`inv_mux`、`inv_cell`、`gate`、`mux`、`cell`、`clk`、`clk_div_with_clken`。原有 family 加子类型的节点写法仍可用；不支持旧 `tree` 外层。

`nodes` 的字典键是节点名，节点体不填写 `name`。节点值为 `null` 或配置 `exclude: true` 时省略；其它节点不能引用被省略的节点。

| 公共字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | | 插件名或兼容的节点类型。 |
| `freq` | `int` | | 频率，单位 Hz；时钟目标省略或填写负值时不限制频率。 |
| `exclude` | `bool` | `false` | 排除节点。 |

### ExtraRegEntry

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `path` | `str` | | 寄存器模型路径，按 `.` 分隔，可带比特范围。 |
| `value` | `int` | | 字段写入值。 |

### Node - source

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `source` | |
| `source_kind` | `str` | `source` | 取 `source`、`pad`。 |
| `freq` | `int` | | 典型频率，单位 Hz；应大于 0。 |

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

固定两路输出，组内共用 **lock**、**pd**、**refdiv**、**fbdiv**，每路各有 **postdiv1**、**postdiv2**。求解按实际分频 1～7 搜系数；写入 **postdiv1**、**postdiv2** 寄存器时为实际分频减 1，分频为 1 时写入 0。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `regs.lock` | `str` | | PLL lock 状态位。 |
| `regs.pd` | `str` | | 掉电控制。 |
| `regs.refdiv` | `str` | | 参考分频系数。 |
| `regs.fbdiv` | `str` | | 反馈分频系数。 |
| `regs.postdiv1[0]` | `str` | | 第 0 路后级分频 1 寄存器写入值，0～6。 |
| `regs.postdiv2[0]` | `str` | | 第 0 路后级分频 2 寄存器写入值，0～6。 |
| `regs.postdiv1[1]` | `str` | | 第 1 路后级分频 1 寄存器写入值，0～6。 |
| `regs.postdiv2[1]` | `str` | | 第 1 路后级分频 2 寄存器写入值，0～6。 |

### Node - clk

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `clk` | |
| `freq` | `int` | | 典型频率，单位 Hz；省略表示不指定频率约束。 |
| `source` | `str` | | 前级引用。 |

### Node - gate

gate 在本工具中必定开启，不接受 `open` 字段；寄存器开启极性由 `gate_reg_high_means_open` 指定。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `gate` | |
| `source` | `str` | | 前级引用。 |
| `reg` | `str` | `""` | 门控寄存器模型路径。 |

### Node - div

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `div` | |
| `div_kind` | `str` | `div` | 取 `div`、`div_n`、`dto`、`dto_n`、`div_r`。 |
| `source` | `str` | | 前级引用。 |
| `ratio` | `int` | | 固定分频比，不配置寄存器；`div_r` 必填，其它型号上限为 64。 |
| `init_ratio` | `int` | | 可编程初始分频比，不与 `ratio` 共用；同时填写 `regs`。 |
| `regs` | `dict` | `{}` | 键由 `div_kind` 决定；`div_r` 保持为空。 |

#### div / div_n

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `regs.rst` | `str` | 复位位。 |
| `regs.load` | `str` | 加载位。 |
| `regs.div` | `str` | 分频系数。 |

#### dto / dto_n

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `regs.rst` | `str` | 复位位。 |
| `regs.load` | `str` | 加载位。 |
| `regs.bypass` | `str` | bypass 位。 |
| `regs.step` | `str` | 步进控制。 |

### Node - inv

反相器仅作频率透传，不写寄存器。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `inv` | |
| `inv_kind` | `str` | `inv` | 取 `inv`、`inv_mux`、`inv_cell`。 |
| `source` | `str` | | 前级引用。 |

### Node - mux

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `mux` | |
| `source` | `dict[str, str]` | `{}` | 非负整数输入编号到前级引用的映射。 |
| `sel` | `int` | | 固定输入编号，不配置选择寄存器。 |
| `init_sel` | `int` | | 可编程初始输入编号，不与 `sel` 共用；同时填写 `reg`。 |
| `reg` | `str` | `""` | 选择寄存器模型路径。 |

### Node - cell

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | `cell` | |
| `cell_kind` | `str` | `cell` | 任意非空字符串，仅作配置记录。 |
| `source` | `str` | | 前级引用。 |

### Node - clk_div_with_clken

三个输出为 `clk_arm_core`、`hclk`、`hclken`。核心输出与 `source` 同频；后两路同频，共用分频比 `ratio`，取 2、3、4、6，可省略交给求解器。寄存器编码分别为 0、2、4、8。

`reg` 可指定分频控制字段；或使用 `regs.div` 并可选 `regs.rst`、`regs.load`。`reg` 与 `regs.div` 同时填写时必须相同。引用输出示例：`bus[hclk]`。
