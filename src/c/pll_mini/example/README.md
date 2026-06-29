# 测试用例

## 提交前

改 **pll_mini** 求解、模型或模板后，在 `example` 目录执行：

```text
check.bat
```

依次跑 **normal.yaml** 与 **cpu_gate_branch.yaml**，**jinja_build** 退出码均为 0 方可提交。

| 步骤 | 文件 | 作用 |
| --- | --- | --- |
| 1 | `normal.yaml` | 健全检查：各 kind 与常见连线形态 |
| 2 | `cpu_gate_branch.yaml` | **cpu_gate** 三路、PLL 参考路径、**gate** 透传链 |

族根 **example.yaml** 与 **normal.yaml** 内容一致，供默认 **jinja_build** 输入。

## 用例表

| 文件 | 预期 |
| --- | --- |
| `normal.yaml` | 健全检查；各 kind 至少一条可解路径。 |
| `cpu_gate_branch.yaml` | **cpu_gate** 多输出、晶振→PLL→分频、**gate** 透传、无频率 **clk**。 |
| `extreme.yaml` | 可解极限压力；多层 mux 组合。 |
| `unsat.yaml` | 故意无解。 |
| `reg_missing_field.yaml` | 寄存器 field 缺失。 |
| `reg_bit_range.yaml` | 寄存器 bit slice 越界。 |
