# 常用 API

类名与方法名均带配置的 `class_prefix` 前缀；下文只写方法 basename。

## load_csv

读取寄存器 CSV，逐行前门写入寄存器模型；默认不向重放口发 payload。若 `emit_replay` 为 1，每行成功后还向重放口发出对应写事务。可消耗仿真时间。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| `filename` | input | `string` | CSV 路径 |
| `clear_dump_first` | input | `bit` | 为 1 则先清空回调累积的待写出写记录 |
| `emit_replay` | input | `bit` | 为 1 时向重放口发出写事务；`init_file` 自动加载时应为 0 |
| `ok` | output | `bit` | 成功为 1 |
