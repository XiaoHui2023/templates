# pll_mini

## 示例

```yaml
regmodel:
  - path: blk_pll_sc.pd
    address: 256
    fields:
      - name: vocpd
        lsb: 0
        width: 1
tree:
  name: main
  nodes:
    xtal:
      kind: source
    pll_sc:
      kind: pll
      source: xtal
      pll_kind: sc
      regs:
        lock: blk_pll_sc.stat.lock
        vocpd: blk_pll_sc.pd.vocpd
      cfg:
        lock: 0
        vocpd: 0
settings:
  main_fn: chip_pll_config
```

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `tree` | `Tree` | 必填 | 单棵时钟树。 |
| `regmodel` | `list[Reg]` | 必填 | 寄存器模型。 |
| `settings` | `Settings` | 见下表 | 全局选项。 |

### Settings

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `main_fn` | `str` | `pll_mini_config` | 配置入口 C 函数名。 |
| `header_guard` | `str` | `PLL_MINI_H` | 头文件 include guard。 |
| `reg_write_fn` | `str` | `pll_mini_reg_write` | 寄存器写函数名。 |
| `gate_reg_high_means_open` | `bool` | `false` | 门控寄存器写 1 是否表示打开。 |
| `div_reg_high_means_reset` | `bool` | `false` | div 的 rst 写 1 是否表示复位。 |
| `dto_reg_high_means_reset` | `bool` | `false` | dto 的 rst 写 1 是否表示复位。 |
| `lock_timeout_us` | `int` | `1000` | PLL lock 轮询超时，微秒。 |

### Reg

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `path` | `str` | 必填 | 寄存器点分路径；点号换为下划线并大写后作 C 宏前缀。 |
| `address` | `int` | 必填 | 寄存器物理地址。 |
| `fields` | `list[Field]` | 必填 | field 列表。 |

### Field

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `name` | `str` | 必填 | field 名。 |
| `lsb` | `int` | 必填 | 最低位索引。 |
| `width` | `int` | 必填 | 位宽。 |

### Tree

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `name` | `str` | 必填 | 时钟树名。 |
| `nodes` | `dict[str, Node]` | 必填 | 节点表，键为节点名。 |

### Node

`kind` 决定节点形状；节点 `regs` 或 `reg` 的值须能在 `regmodel` 中解析到对应 field。

| `kind` | 主要字段 | 说明 |
| --- | --- | --- |
| `source` | — | 时钟源。 |
| `pll` | `source`, `pll_kind`, `regs`, `cfg` | 固化 PLL 各 reg 键写入值；`cfg` 键须与 `regs` 允许集合一致。 |
| `div` | `source`, `regs`, `cfg` | `cfg` 须含 `div`；rst 与 load 脉冲由生成顺序自动插入。 |
| `dto` | `source`, `regs`, `cfg` | `cfg` 须含 `load`、`bypass`、`step`。 |
| `gate` | `source`, `reg`, `open` | 固化门开闭。 |
| `mux` | `source`, `reg`, `sel` | 固化选择值。 |
| `inv` | `source` | 反相，无寄存器配置。 |
| `clk` | `source` | 时钟出口，无寄存器配置。 |

配置顺序与 clock_tree **config_reg** 相同：全部 **pll** 写寄存器后 **wait_lock**；全部 **div** 与 **dto**；**open** 为真的 **gate**；全部 **mux**；**open** 为假的 **gate**。

生成的 **pll_mini.c** 为每次寄存器写列出各 field 切片的 **lsb**、**width** 与语义 **value**，并附带 Python 合并后的整字 **reg_word**；改 YAML 后重新展开即可同步。
