# 常用 API

类名与方法名均带配置的 `class_prefix` 前缀；下文只写方法 basename。

## load_csv

读取寄存器 CSV，逐行前门写入寄存器模型。读文件或任一行提交失败时打 `UVM_ERROR` 并中止。

| 参数 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| `filename` | input | `string` | CSV 路径 |

## clear_dump

若已通过 `uvm_config_db` 向本 sequencer 提供了 `reg_mon_cb`（`{{ class_prefix }}reg_monitor_cb`），则调用其 `clear_dump_rows()`，清空回调里累积的待写出写记录；未绑定或无实例则为空操作。需要在加载 CSV 前先清空时，由调用方显式调用本方法。
