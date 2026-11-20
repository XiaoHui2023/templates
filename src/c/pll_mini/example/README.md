# 配置示例

| 输入文件 | 内容 |
| --- | --- |
| `../example.yaml` | 多型号节点、共享分频、多层 mux 和 PLL 参考路径。 |
| `normal.yaml` | 较小的可解时钟树。 |
| `initialization.yaml` | 启用必须目标，指定备用分频初值和同频输入的来源。 |
| `exclusion.yaml` | 正常与排除路径并存，共用寄存器只保留正常字段。 |
| `extreme.yaml` | 多层 mux 与并行分频的压力输入。 |
| `unsat.yaml` | 无解频率关系。 |
| `reg_bit_range.yaml` | 寄存器比特范围错误。 |
| `reg_missing_field.yaml` | 不存在的寄存器字段。 |

`initialization.yaml` 与 `exclusion.yaml` 使用 `normal.ralf` 中的寄存器定义；路径以输入 YAML 所在目录为起点。
