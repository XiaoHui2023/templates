# example 目录

提交前跑 **example\check.bat**：**normal.yaml** 经 **jinja_build** 退出码为 0。

| 步骤 | 文件 | 用途 |
| --- | --- | --- |
| 1 | `normal.yaml` | 健全检查：各 kind 与常见连线形态 |

族根 **example.yaml** 与 **normal.yaml** 内容一致，供默认 **jinja_build** 输入。

## 其它样例

| 文件 | 用途 |
| --- | --- |
| `normal.yaml` | 健全检查；各 kind 至少一条可解路径。 |
| `extreme.yaml` | 压力岛、多层 mux 组合、共享 **div** |
| `unsat.yaml` | 故意无解拓扑，验收诊断输出 |
| `reg_bit_range.yaml` | 寄存器位宽越界报错 |
| `reg_missing_field.yaml` | 缺少寄存器 field 报错 |
