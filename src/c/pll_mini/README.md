# pll_mini

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
| `ralf` | `str` | 必填 | RALF 文件路径；相对路径先相对 YAML 所在目录，再相对模板单元目录查找。 |
| `ralf_include_dirs` | `list[str]` | `[]` | ralf-conv 解析 `source` 时的额外搜索目录。 |
| `ralf_base_offset` | `int` | `0` | 加到 ralf-conv 输出的全部寄存器绝对地址上的字节偏移。 |
| `tree` | `Tree` | 必填 | 单棵时钟树；节点字段与 clock_tree 同形，不含 RTL `path` 与仿真度量项。 |
| `settings` | `Settings` | 见下表 | 全局选项。 |

### Settings

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `main_fn` | `str` | `pll_mini_config` | 配置入口 C 函数名；经 DPI-C 导出供 SystemVerilog `import`。 |
| `header_guard` | `str` | `PLL_MINI_H` | 头文件 include guard。 |
| `gate_reg_high_means_open` | `bool` | `false` | 门控寄存器写 1 是否表示打开。 |
| `div_reg_high_means_reset` | `bool` | `false` | div 的 rst 写 1 是否表示复位。 |
| `dto_reg_high_means_reset` | `bool` | `false` | dto 的 rst 写 1 是否表示复位。 |
| `pll_sc_fbdiv_min` | `int` | `16` | 允许 PLL SC FBDIV 下限。 |
| `pll_sc_fbdiv_max` | `int` | `84` | 允许 PLL SC FBDIV 上限。 |
| `consolver_timeout_ms` | `int` | 省略 | consolver 求解超时，毫秒。 |

### Tree

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `name` | `str` | 必填 | 时钟树名。 |
| `nodes` | `dict[str, Node]` | 必填 | 节点表，键为节点名。 |

至少含一个 `kind: clk` 节点；各 clk 的 `freq` 锚定该输出频率，求解器同时为全部 clk 选取活动路径、mux 选择与分频比。

### Node

`kind` 决定节点形状；`regs` 或 `reg` 非空时都要能在 RALF 转出的寄存器模型中解析。门控开闭、mux 选择、div/dto 分频比与 PLL 各 field 写入值由频率约束求解后推算，不在 YAML 填写。

| `kind` | 主要字段 | 说明 |
| --- | --- | --- |
| `source` | `freq` | 时钟源频率，单位 Hz。 |
| `pll` | `source`, `pll_kind`, `freq`, `regs` | 目标输出频率；`regs` 键集合与型号一致。 |
| `div` | `source`, `regs` | 分频比由约束求解确定。 |
| `dto` | `source`, `regs` | 分频比由约束求解确定。 |
| `gate` | `source`, `reg` | 活动路径上门打开，其余关闭。 |
| `mux` | `source`, `reg` | 选择能同时满足全部 clk 的输入标签。 |
| `inv` | `source` | 反相，无寄存器。 |
| `clk` | `source`, `freq` | 输出频率锚点，单位 Hz。 |

配置顺序与 clock_tree **config_reg** 相同：全部活动 **pll** 写寄存器后统一等待 lock；活动 **div** 与 **dto**；打开的 **gate**；活动 **mux**；关闭的 **gate**。

同 **pll_kind** 且 **output_count** 相同的活动节点，寄存器路径后缀与 field 位域布局必须一致，否则 Python 校验报错。同一输出频率在不同节点上推算的分频也要一致。

每种 **pll_kind** 生成一个通用函数 **pll_mini_config_pll_***，参数为各寄存器块 64 位地址与 **out_freq_hz**；函数内 **switch** 枚举该型号在时钟树中出现过的输出频率。每个活动 PLL 实例在 **chip_pll_config** 中传入本实例地址宏与目标频率；**pll_mini_config_steps** 仍只列 **div**、**dto**、**gate**、**mux**。

寄存器读写通过 DPI 从 SystemVerilog 导入 **cpu_config_read**、**cpu_config_write**；地址为 64 位，数据为 32 位。**main_fn** 在 C 侧 `export "DPI-C"`，仿真中 `import "DPI-C" context function void <main_fn>();`。SystemVerilog 以 `export "DPI-C" function int unsigned cpu_config_read(input longint unsigned addr);` 与 `export "DPI-C" function void cpu_config_write(input longint unsigned addr, input int unsigned data);` 提供读写实现。

模板单元 **`bin/linux/`** 含 consolver 与 ralf-conv 的 Linux 单文件可执行体；Git 已标记可执行，克隆后在 Ubuntu 上可直接配合 jinja-build 使用，无需 `chmod`。Windows 上在本仓库内跑 jinja-build 时使用 **`test/c/pll_mini/bin/windows/`** 中的可执行体；也可通过环境变量 **`PLL_MINI_BIN_DIR`** 指定其它目录。
