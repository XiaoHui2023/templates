# 输入配置

根对象由 `settings` 和 `nodes` 组成。节点可独立保存，用 `nodes: !include example_nodes.yaml` 引入。

## 示例

```yaml
settings:
  class_regmodel: chip_regmodel

nodes:
  osc:
    kind: source
    frequence: 24000000

  gate_cpu:
    kind: gate
    source: osc
    reg: clk_ctrl.cpu_gate
    open: 1

  clk_cpu:
    kind: clk
    source: gate_cpu
    path: dut.clk_cpu
    stable: true
```

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `settings` | `Settings` | 默认设置 | 全局选项。 |
| `nodes` | `dict[str, Node]` | | 按名字管理的节点。 |

### Settings

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `class_prefix` | `str` | `clk_tree_` | 类型名前缀。 |
| `class_regmodel` | `str` | `""` | 寄存器模型类型名。 |
| `direct_config` | `bool` | `false` | 启用独立的纯寄存器配置用法。 |
| `min_freq_hz` | `int` | `15000` | 允许最低频率，单位 Hz。 |
| `max_freq_hz` | `int` | `5000000000` | 允许最高频率，单位 Hz。 |
| `active_cycles` | `int` | `1` | 活动判定周期数。 |
| `stable_cycles` | `int` | `3` | 稳定判定周期数。 |
| `period_tolerance` | `float` | `0.02` | 周期相对误差。 |
| `duty_min` | `float` | `48.0` | 占空比下限。 |
| `duty_max` | `float` | `67.0` | 占空比上限。 |
| `duty_tolerance_pct` | `float` | `0.05` | 占空比容差。 |
| `plugin` | `dict[str, dict]` | `{}` | 节点插件的全局选项。 |

`settings.plugin.<作用域>` 由注册插件校验；例如 `settings.plugin.pll_sc.fbdiv_max`。

### 前级引用

| 写法 | 含义 |
| --- | --- |
| `pll_cpu` | 单输出前级。 |
| `pll_cpu[core]` | 多输出节点的 `core` 输出组。 |
| `{ "0": "xtal", "1": "pll_cpu" }` | 按输入端口键指定多个前级。 |

### 寄存器模型路径

| 写法 | 含义 |
| --- | --- |
| `blk.field` | 整个字段。 |
| `blk.field[1]` | 单个比特。 |
| `blk.field[7:0]` | 连续位段。 |

### Node

#### 公共字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | | 节点插件名。 |
| `exclude` | `bool` | `false` | 排除该节点，不生成实例、接口和寄存器绑定。 |
| `expected_activity` | `auto` / `static` / `toggling` | 由插件决定 | 覆盖低功耗配置后的 route 输出活动预期；同一节点的各展开实例共用。 |
| `source` | `str` / `dict[str, str]` | | 前级引用。 |
| `outputs` | `list[str]` | `[]` | 输出组。 |
| `path` | `str` | | 信号测量路径。 |
| `in_path`、`out_path` | `str` | | 默认输入、输出路径。 |
| `in_paths`、`out_paths` | `dict[str, str]` | `{}` | 具名端口路径。 |
| `reg` | `str` | | 默认寄存器模型路径。 |
| `regs` | `dict[str, str]` | `{}` | 具名寄存器模型路径。 |
| `output_regs` | `dict[str, dict[str, str]]` | `{}` | 按输出组覆盖的寄存器路径。 |
| `output_config` | `dict[str, dict]` | `{}` | 按输出组覆盖的插件配置。 |

#### 插件配置

插件字段与公共字段平级，由对应 Python 插件定义和校验。已注册插件的字段拼错或多写会报错。不再使用 `config` 容器。

| `kind` | 字段 |
| --- | --- |
| `source`、`source_pad` | `frequence` |
| `pll_sc`、`pll_dw`、`pll_inno`、`pll_tci` | `frequence`、`enabled`；`pll_inno` 还支持 `group_id` |
| `clk` | `frequence`、`enabled`、`low_power`、`stable`、`check_duty`、`unfix_frequence`、`unfix_enabled` |
| `cell` | `cell_kind`、`frequence`、`enabled` |
| `gate` | `open`、`unfix_open`、`fix_open`、`fix_close` |
| `mux`、`inv_mux` | `max_sel`、`sel`、`unfix_sel` |
| `div_div` | `ratio`、`unfix_ratio` |
| `div_div_r`、`div_dto` | `ratio`、`unfix_ratio` |
| `clk_div_with_clken` | `ratio`、`unfix_ratio`，ratio 为 2、3、4 或 6 |
| `inv`、`inv_cell` | `inverted`、`fix_inverted` |

`stable: true` 且省略 enabled 时补 1；显式 enabled 小于等于 0 会报错。`exclude: true` 不等于关闭时钟；引用该节点的 source 连接会被忽略，其他节点和连接保留。

mux 的选择值来自 source 的实际键集合。键使用非负整数的十进制字符串；例如只有 `"2"`、`"5"` 时，只允许选择 2 或 5。省略 max_sel 不增加上限，填写后只缩小该集合。

`inv_mux` 与 `mux` 使用相同的选择配置和检查，不执行反相检查；切换等待使用 `settings.plugin.mux`。

## 固定节点与可编程节点

mux、gate 和分频器可以由寄存器控制，也可以接固定电平。固定节点填写 `sel`、`open` 或正数 `ratio`，不填寄存器，不解除对应固定要求。

```yaml
nodes:
  mux_fixed:
    kind: mux
    source: {"0": osc, "1": pll_cpu}
    sel: 0

  mux_programmable:
    kind: mux
    source: {"0": osc, "1": pll_cpu}
    reg: clk_ctrl.cpu_sel
    sel: 1
```

可编程节点填写控制字段；`sel`、`open`、`ratio` 是目标，省略时由约束求解。只填部分寄存器会报错。

| 节点 | 启用寄存器配置时必须绑定 | 可选寄存器 |
| --- | --- | --- |
| mux、inv_mux、gate、可编程反相器 | `reg` | |
| div_div | `rst`、`load`、`div` | |
| div_dto | `rst`、`load`、`bypass`、`step` | |
| clk_div_with_clken | `div` 或 `reg` | `rst`、`load` |
| pll_sc | `lock`、`vocpd`、`postdivpd`、`dsmpd`、`pd`、`bypass`、`refdiv`、`postdiv2`、`postdiv1`、`fbdiv` | |
| pll_inno | `lock`、`pd`、`postdiv1`、`refdiv`、`postdiv2`、`fbdiv` | |
| pll_tci | `lock`、`bypass`、`pwrdn`、`reset`、`clkod`、`clkf`、`clkr`、`bwadj` | |
| pll_dw | `lock`、`fbdiv`、`prediv`、`reset`、`pwron`、`shift`、`bypass`、`divvcor`、`r`、`p`、`divvcop`、`enr`、`enp` | |

`div_div_r` 不支持寄存器。反相器不填寄存器时按 `inverted` 固定，省略为反相。PLL 不填寄存器时表示外部固定时钟，填写正频率或明确关闭；填写寄存器则必须提供对应型号的完整字段。全部节点均无需寄存器时，可以省略 `class_regmodel`。

## 插件设置

### mux 切换等待

`settings.plugin.mux`：

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `switch_cycles` | `8` | 写 sel 后等待旧、新输入中最慢时钟的周期数。 |
| `switch_timeout_ns` | `1000000` | 等待预算上限，单位 ns；超过则报错，不继续写 sel。 |

`switch_cycles` 应覆盖目标 IP 的同步延迟；等待时间按旧、新输入中最慢的频率计算，不表示读取了硬件完成状态。

### DTO 配置

`settings.plugin.div_dto` 支持以下选项。

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `reg_high_means_reset` | `false` | 复位高有效。 |
| `reset_on_config` | `false` | 每次配置前复位。 |
| `sync_wait_ns` | `200` | 复位和 load 同步等待时间，单位 ns，大于 0。 |
| `settle_ns` | `200` | flip 测量前的稳定等待时间，单位 ns。 |

`sync_wait_ns` 应覆盖目标 IP 的复位和 load 同步延迟，不表示读取了硬件完成状态。

### 其他插件设置

均写在 `settings.plugin.<作用域>` 下。

| 作用域 | 字段 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `divider` | `freq_tolerance` | `0.01` | 分频约束容差，支持 0.005、0.0005 等小数；不改变测量误差 |
| `div_div` | `reg_high_means_reset` | `false` | 复位高有效 |
| `div_div` | `reset_on_config` | `false` | 普通配置前复位 |
| `div_div` | `settle_ns` | `200` | flip 测量前等待时间，ns |
| `gate` | `reg_high_means_open` | `false` | 寄存器 1 表示打开 |
| `inverter` | `reg_high_means_inverted` | `true` | 寄存器 1 表示反相 |
| `inverter` | `settle_ns` | `100` | 配置极性后采样前等待时间，ns |
| `pll` | `lock_timeout_us` | `100` | 首次锁检查开始后的等待预算，us |

### SC PLL 搜索

`settings.plugin.pll_sc`：

| 字段 | 默认值 | 含义 |
| --- | --- | --- |
| `fbdiv_min` | `16` | 反馈分频下限 |
| `fbdiv_max` | `99` | 反馈分频上限 |
| `pfd_min_hz` | `12000000` | 鉴相频率下限，Hz |
| `vco_min_hz` | `800000000` | VCO频率下限，Hz |
| `vco_max_hz` | `1600000000` | VCO频率上限，Hz |
| `freq_tolerance` | `0.02` | 最优合法解允许的相对输出误差 |

边界应按目标 IP 设置；允许误差只判断可接受性，不降低最佳频率搜索精度。

### 共享寄存器

绑定同一寄存器字段及相同比特范围的分频节点，实际写入编码必须一致。分频比显式要求互相矛盾时，随机化失败，不会分别配置后相互覆盖。reset 和 load 是控制动作，不用于约束分频比。

### 输出组覆盖

多输出节点用 `output_config` 覆盖指定输出组，未覆盖的字段沿用节点顶层值。

```yaml
nodes:
  pll_audio:
    kind: pll_inno
    outputs: [fast, slow]
    frequence: 480000000
    output_config:
      slow:
        frequence: 240000000
```

### clk_div_with_clken

```yaml
nodes:
  bus_div:
    kind: clk_div_with_clken
    source: osc
    in_path: dut.bus_div_i
    out_paths:
      clk_arm_core: dut.clk_arm_core
      hclk: dut.hclk
      hclken: dut.hclken
    regs:
      div: clk_ctrl.divider[3:0]
      rst: clk_ctrl.reset
      load: clk_ctrl.load
    ratio: 3
```

三个输出名固定，无需填写 outputs。clk_arm_core 直通输入，hclk 和 hclken 共用分频。div 绑定四位字段，rst 和 load 可省略；仅有分频字段时也可使用 reg。全局 `settings.plugin.clk_div_with_clken` 支持 `reg_high_means_reset` 和 `settle_ns`，默认分别为 false 和 200。

| 编码 | 分频比 |
| --- | --- |
| `000x` | 2 |
| `001x` | 3 |
| `01xx` | 4 |
| `1xxx` | 6 |
