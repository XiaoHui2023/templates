# 全局 function，memh 辅助

同包还提供若干 **`function automatic`**，完整名称为 **`<class_prefix>` 与下表方法名连接而成**；`class_prefix` 与 **agent** 所用类型名前缀一致。下表与下文各节标题只写方法名本身，不重复前缀。

下列函数与 **agent** 里 **sequencer** 的对应成员方法一致，可在不持有 **sequencer** 的场景中直接使用。

## `read_memh_file`

读 memh 文件，将内容写入形参 **`dst`** 所指的关联数组。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `filename` | input | `string` |  | memh 路径 |
| `dst` | ref | `bit [7:0] dst[bit [63:0]]` |  | 输出：字节地址到 8 位值 |
| `clear_first` | input | `bit` |  | 为真则先清空 `dst` |

**返回值：** `bit` — 成功为 1，失败为 0。

## `read_memh_file_to_byte_q`

读 memh 后，从 `start_addr` 起按地址连续取字节写入队列 `q`。

- 未给出 `len` 时，读到第一个没有数据的字节地址为止。
- 给出非负 `len` 时，这一段内每个地址都必须有数据，否则判失败。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `filename` | input | `string` |  | memh 路径 |
| `q` | output | `bit [7:0] q[$]` |  | 输出字节队列 |
| `start_addr` | input | `bit [63:0]` |  | 起始字节地址 |
| `len` | input | `int` |  | 字节个数；省略表示连读直到遇到没有数据的地址 |

**返回值：** `bit` — 成功为 1，失败为 0。

## `write_memh_file`

把 **字节地址到 8 位值** 的存储写成 memh 文件。每行最多几个数据字节由配置里的行宽项决定，**不在**本函数形参中出现。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `filename` | input | `string` |  | 输出路径 |
| `src` | ref | `bit [7:0] src[bit [63:0]]` |  | 数据来源 |

**返回值：** `bit` — 成功为 1，失败为 0。

## `compare_memory`

按 `compare_type` 比较两份 **字节地址到 8 位值** 形式的存储。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `actual` | ref | `bit [7:0] actual[bit [63:0]]` |  | 参与比较的 **`actual`** 字节图 |
| `expected` | ref | `bit [7:0] expected[bit [63:0]]` |  | 参与比较的 **`expected`** 字节图 |
| `expected_name` | input | `string` |  | 上述 **`expected`** 在提示中的显示名 |
| `compare_type` | input | `compare_type_e` | `STRICT` | `SUBSET`、`STRICT`、`SUPERSET`、`INTERSECT`，含义与 settings 中同名枚举一致 |

**返回值：** `bit` — 满足比对规则为 1，否则为 0。

## `compare_memh_file`

从 memh 文件读出期望数据，再与 `actual` 按 `compare_type` 比较。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `actual` | ref | `bit [7:0] actual[bit [63:0]]` |  | 参与比较的 **`actual`** 字节图 |
| `filename` | input | `string` |  | 期望 memh 路径 |
| `compare_type` | input | `compare_type_e` | `STRICT` | 同 `compare_memory` |

**返回值：** `bit` — 满足比对规则为 1，否则为 0。
