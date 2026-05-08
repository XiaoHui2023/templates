# 常用 API

类名与方法名均带配置的 `class_prefix` 前缀；下文只写方法 basename。

## load_csv

读取寄存器 CSV，逐行前门写入寄存器模型并更新镜像；`dump_file` 非空时将行记入待写出队列；并向 `o_ap` 发出对应写事务。可消耗仿真时间。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `filename` | input | `string` |  | CSV 路径 |
| `clear_dump_first` | input | `bit` | `0` | 为 1 则先清空待写出行队列再加载 |
| `ok` | output | `bit` |  | 成功为 1，失败为 0 |

## clear_dump_rows

清空当前待写出的 CSV 行队列（不影响寄存器模型镜像）。

## append_dump_row

向待写出队列追加一行（点分路径与数值文本），便于测试手写记录。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | input | `string` |  | 点分寄存器路径 |
| `value_text` | input | `string` |  | 与 CSV 第二列同风格的数值字符串 |

## row_to_payload

将单行 CSV 记录转为 `uvm_tlm_generic_payload`（不写寄存器模型、不记入待写出队列）。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `row` | input | 带前缀的 `csv_row` 句柄 |  | 路径与数值文本 |
| `payload` | output | `uvm_tlm_generic_payload` |  | 输出写事务 |

**返回值：** `bit` — 成功为 1，失败为 0。
