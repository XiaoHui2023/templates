# 常用 API

类名与方法名均带配置的 `class_prefix` 前缀；下文只写方法 basename。

## load_csv

读取寄存器 CSV，逐行前门写入寄存器模型。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| `filename` | input | `string` | CSV 路径 |
| `clear_dump_first` | input | `bit` | 为 1 则先清空回调累积的待写出写记录 |
| `ok` | output | `bit` | 成功为 1 |
