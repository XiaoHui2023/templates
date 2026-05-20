# API

类名与方法名均带配置的 `class_prefix` 前缀；下文只写方法 basename。

## `imp` 与 `memory`

| 成员 | 说明 |
| --- | --- |
| `memory` | 按 64 位字节地址保存 8 位数据；未写过的地址视为无数据。 |
| `imp` | 收到 `uvm_tlm_generic_payload` 后按地址与数据写入 `memory`。 |
| `o_ap` | `write_payload` 完成后把同一份 payload 再发出去。 |
| `o_load_ap` | `load_file` 时按连续地址段发出写事务，仍为 generic payload。 |

## `load_file`

从 memh 文件加载到 `memory`，并向 `o_load_ap` 发出本次加载对应的写事务。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `filename` | input | `string` |  | memh 文件路径 |
| `clear_first` | input | `bit` |  | 为真时先清空当前 `memory` |

**返回值：** `bit` — 成功为 1，失败为 0。

## `save_file`

把当前 `memory` 写成 memh 文件。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `filename` | input | `string` |  | 输出文件路径 |

写出时每行最多几个数据字节由配置里的行宽项决定，与同包 **`write_memh_file`** 一致；**不在** `save_file` 与 **`write_memh_file`** 的形参中出现。

**返回值：** `bit` — 成功为 1，失败为 0。

## `write`

按 `uvm_tlm_generic_payload` 的地址与数据写入 `memory`，克隆后调用 `write_payload`，再由 `o_ap` 发出。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `payload` | input | `uvm_tlm_generic_payload` |  | 待写入事务 |

## `write_payload`

写入 `uvm_tlm_generic_payload`。与 `write` 不同，本方法不克隆对象；生命周期与复用由调用方自行约束。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `payload` | input | `uvm_tlm_generic_payload` |  | 要写入的 payload |

## `read_payload`

读取 `uvm_tlm_generic_payload`，READ 语义，数据与地址填入新 payload。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `addr` | input | `bit [63:0]` |  | 起始字节地址 |
| `len` | input | `int` |  | 字节数 |
| `name` | input | `string` |  | 新 payload 的对象名 |

**返回值：** `uvm_tlm_generic_payload`。

## `write_data`

从起始地址起写入一段字节队列。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `addr` | input | `bit [63:0]` |  | 起始字节地址 |
| `data` | input | `bit [7:0] data[$]` |  | 字节队列 |

## `read_data`

从起始地址起顺序读 `len` 个字节；某地址从未写入则用 `default_value` 填入队列。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `addr` | input | `bit [63:0]` |  | 起始字节地址 |
| `len` | input | `int` |  | 字节数 |
| `default_value` | input | `bit [7:0]` |  | 未写过地址的填充值 |

**返回值：** 通过 `output` 形参 `data_q` 传出 `bit [7:0][$]`，长度等于 `len`。

## `write_byte`

写入单字节。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `addr` | input | `bit [63:0]` |  | 字节地址 |
| `data` | input | `bit [7:0]` |  | 数据 |

## `read_byte`

读取单字节。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `addr` | input | `bit [63:0]` |  | 字节地址 |
| `default_value` | input | `bit [7:0]` |  | 未写过地址时返回的值 |

**返回值：** `bit [7:0]`。

## `compare_file`

与 memh 文件比较，不满足当前比对规则时上报 `uvm_error`。比较前在 **memory** 与期望地址并集上按连续段读出（缺址用读路径默认填充），并调用 **`after_read_data`**。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `filename` | input | `string` |  | 期望 memh 路径 |

**返回值：** `bit` — 满足比对规则为 1，否则为 0。

## `compare_memory`

与另一份 **字节地址到 8 位值** 形式的期望数据比较，不满足当前比对规则时上报 `uvm_error`。比较前在 **memory** 与 **expected** 地址并集上按连续段读出（缺址用读路径默认填充），并调用 **`after_read_data`**。期望由参数 **`expected`** 给出。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `expected` | ref | `bit [7:0] expected[bit [63:0]]` |  | 期望数据 |
| `expected_name` | input | `string` |  | 报错里指称 **expected** 数据所用的名字 |

**返回值：** `bit` — 满足比对规则为 1，否则为 0。

## `clear`

清空当前 `memory`。
