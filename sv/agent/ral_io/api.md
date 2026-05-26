# API

类名与方法名均带配置的 `class_prefix` 前缀；下文只写方法 basename。

## load_csv

读取寄存器 CSV，逐行前门写入寄存器模型；任一步失败则中止。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| `filename` | input | `string` | CSV 路径 |

## clear_dump

在加载新的寄存器 CSV 之前可调用，用于丢弃尚待写出的寄存器写记录；无可丢弃内容则无操作。
