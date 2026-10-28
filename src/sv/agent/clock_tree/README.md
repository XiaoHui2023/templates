# clock_tree

## 示例

```yaml
settings:
  class_regmodel: chip_regmodel

nodes:
  osc:
    kind: source
    config:
      frequence: 24000000

  gate_cpu:
    kind: gate
    source: osc
    reg: clk_ctrl.cpu_gate
    config:
      open: 1

  clk_cpu:
    kind: clk
    source: gate_cpu
    path: dut.clk_cpu
    config:
      stable: true
```

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `settings` | `Settings` | | 全局选项。 |
| `nodes` | `dict[str, Node]` | | 按名字管理的节点。 |

### Settings

节点可独立保存，用 `nodes: !include example_nodes.yaml` 引入。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `class_prefix` | `str` | `clk_tree_` | 类型名前缀。 |
| `class_regmodel` | `str` | `""` | 寄存器模型类型名。 |
| `direct_config` | `bool` | `false` | 生成轻量配置入口。 |
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
节点私有字段只写在 `config` 或 `output_config`，不再写到节点顶层。

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
| `source` | `str` / `dict[str, str]` | | 前级引用。 |
| `outputs` | `list[str]` | `[]` | 输出组。 |
| `path` | `str` | | 观测路径。 |
| `in_path`、`out_path` | `str` | | 默认输入、输出路径。 |
| `in_paths`、`out_paths` | `dict[str, str]` | `{}` | 具名端口路径。 |
| `reg` | `str` | | 默认寄存器模型路径。 |
| `regs` | `dict[str, str]` | `{}` | 具名寄存器模型路径。 |
| `output_regs` | `dict[str, dict[str, str]]` | `{}` | 按输出组覆盖的寄存器路径。 |
| `config` | `dict` | `{}` | 节点插件配置。 |
| `output_config` | `dict[str, dict]` | `{}` | 按输出组覆盖的插件配置。 |

#### 插件配置

| `kind` | `config` 字段 |
| --- | --- |
| `source`、`source_pad` | `frequence` |
| `pll_sc`、`pll_dw`、`pll_inno`、`pll_tci` | `frequence`、`enabled`；`pll_inno` 还支持 `group_id` |
| `clk` | `frequence`、`enabled`、`low_power`、`stable`、`check_duty`、`unfix_frequence`、`unfix_enabled` |
| `cell` | `cell_kind`、`frequence`、`enabled` |
| `gate` | `open`、`unfix_open`、`fix_open`、`fix_close` |
| `mux` | `max_sel`、`sel`、`unfix_sel` |
| `div_div` | `ratio`、`unfix_ratio` |
| `div_div_r`、`div_dto` | `ratio`、`unfix_ratio` |
| `clk_div_with_clken` | `ratio`、`unfix_ratio`，ratio 为 2、3、4 或 6 |
| `inv`、`inv_cell`、`inv_mux` | `inverted`、`fix_inverted` |

`stable: true` 且省略 enabled 时补 1；显式 enabled 小于等于 0 会报错。`exclude: true` 不等于关闭时钟；保留的节点不能引用被排除的节点。

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
    config:
      ratio: 3
```

三个输出名固定，无需填写 outputs。clk_arm_core 直通输入，hclk 和 hclken 共用分频。div 绑定四位字段，rst 和 load 可省略；仅有分频字段时也可使用 reg。全局 `settings.plugin.clk_div_with_clken` 支持 `reg_high_means_reset` 和 `settle_ns`，默认分别为 false 和 200。

| 编码 | 分频比 |
| --- | --- |
| `000x` | 2 |
| `001x` | 3 |
| `01xx` | 4 |
| `1xxx` | 6 |
