# clock_tree

## 示例

```yaml
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
    frequence: 24000000
    enabled: 1

settings:
  class_regmodel: chip_regmodel
```

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `settings` | `Settings` | | 全局选项。 |
| `<节点名>` | `Node` | | 节点定义。 |

### Settings

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
| `present` | `bool` | `true` | 是否生成节点。 |
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
| `inv`、`inv_cell`、`inv_mux` | `inverted`、`fix_inverted` |
