# clock_tree

## 相关文档

[数据模型](model.md)

[节点 interface](interface.md)

## 示例

```yaml
class_prefix: chip_clk_
setting_defs:
  - name: pll_sel
    type: int
    default: 0
trees:
  - name: main
    settings:
      pll_sel: 0
    nodes:
      osc:
        kind: source
        targets: [pll0]
      pll0:
        kind: pll
        targets: [clk_cpu]
        freq: 1000000000
      clk_cpu:
        kind: clk
        source: pll0
```

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `class_prefix` | `str` | `clk_tree_` | 命名前缀。没有重名风险时可保持默认。 |
| `setting_defs` | `list[SettingDef]` | `[]` | 全局设置项声明，每棵 tree 的 `settings` 使用同一组键。 |
| `trees` | `list[Tree]` | 必填 | 时钟树列表，至少填写一棵。 |
| `vars` | `dict[str, Any]` | `{}` | 自定义变量，未使用时留空。 |
| `class_regmodel` | `str` | `""` | RAL 根块类名称，节点填写寄存器路径时需要设置。 |

### 寄存器路径

`reg` 与 `regs` 的值为自 RAL 根起的点分路径，可在末尾指定 field 内比特范围：

| 写法 | 含义 |
| --- | --- |
| `blk.field` | 整个 field；offset 为 0，width 为 field 位宽 |
| `blk.field[1]` | 仅 bit 1，位宽 1 |
| `blk.field[3:0]` | 从 lsb 0 起连续 4 位 |

**configure** 只更新所列比特，field 内其余位保持不变。
| `min_freq_hz` | `int` | `500` | 判断时钟仍在活动的最低频率。 |
| `stable_cycles` | `int` | `3` | 连续稳定周期数。 |
| `period_tolerance` | `float` | `0.05` | 相邻周期相对偏差上限。 |
| `duty_min` | `float` | `0.50` | 允许占空比下限。 |
| `duty_max` | `float` | `0.66` | 允许占空比上限。 |

### SettingDef

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `name` | `str` | 必填 | 设置项名，也是每棵 tree 的 `settings` 键名。 |
| `type` | `str`, `int`, `bit` | 必填 | 设置项成员类型。 |
| `default` | `Any` | 必填 | 设置项默认取值。 |

### Tree

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `name` | `str` | 必填 | 时钟树名称。 |
| `settings` | `dict[str, int]` | `{}` | 本棵时钟树的设置项取值，键与 `setting_defs.name` 一致。 |
| `nodes` | `dict[str, Node]` | 必填 | 本棵时钟树的节点表，键为节点 name，节点体内勿填 name。 |

### Node

所有节点都可以填写下列公共字段。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | 必填 | 节点类型。 |
| `name` | `str` | — | 由 `nodes` 字典键注入，配置中勿填。 |
| `path` | `str` | `""` | RTL 层次路径，仅用于 **connection** 展开；不写入节点类。留空则不生成 interface。 |
| `allow_bad_duty` | `bool` | `false` | 为真时放宽占空比检查。 |
| `freq` | `optional int` | `null` | 典型频率。 |

| `kind` | 主要字段 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `source` | `targets` | `targets` 必填 | 时钟源节点，`targets` 写目标节点名列表。 |
| `pll` | `targets`, `pll_kind`, `regs` | `targets`、`pll_kind` 必填 | PLL 节点；`pll_kind` 为 `tci`、`sc`、`dw` 之一，大小写不限；`regs` 为逻辑名到 RAL 路径的映射，值可带比特范围后缀，非空时键须与该 `pll_kind` 允许集合完全一致。 |
| `clk` | `source` | `source` 必填 | 时钟输出节点，`source` 写前级节点名。 |
| `gate` | `source`, `target`, `reg` | `source` 与 `target` 必填 | 门控节点；`reg` 为可选 RAL 点分路径，可带比特范围后缀。 |
| `div` | `source`, `target`, `regs` | `source` 与 `target` 必填 | 分频节点；`regs` 非空时键为 `rst`、`load`、`div`，值可带比特范围后缀。 |
| `dto` | `source`, `target`, `regs` | `source` 与 `target` 必填 | DTO 节点；`regs` 非空时键为 `rstn`、`load`、`bypass`、`step`，值可带比特范围后缀。 |
| `inv` | `source`, `target` | `source` 与 `target` 必填 | 反相节点，`source` 写前级节点名，`target` 写输出连线名。 |
| `mux` | `source`, `target`, `sel`, `reg` | `source` 与 `target` 必填，`sel` 省略时取 `settings.pll_sel`，没有该键则为 `0` | 多路选择节点；`reg` 为可选 RAL 路径，可带比特范围后缀。 |
