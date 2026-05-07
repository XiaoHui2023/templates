# 全局 function（memh 辅助）

本族在 `functions.sv` 里生成若干 **`function automatic`**，符号名为 **`<class_prefix>` + 下表中的基名**（`<class_prefix>` 来自 `models.py` 的 `class_prefix`）。**下文标题与参数表只写基名**，避免在每个小节重复写前缀。

实现上委托给同包的引擎类：**基名** `memh_engine`，生成时类型名为 `<class_prefix>memh_engine`；与 [Sequencer API](memh_io_api.md) 无调用关系时可单独使用下列函数。

## `read_memh_file`

读 memh 文件，把结果放进调用方提供的关联数组 `dst`。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `filename` | input | `string` |  | memh 路径 |
| `dst` | ref | `bit [7:0] dst[bit [63:0]]` |  | 输出：字节地址到 8 位值 |
| `clear_first` | input | `bit` |  | 为真则先清空 `dst` |

**返回值：** `bit` — 成功为 1，失败为 0。

## `read_memh_file_to_byte_q`

读 memh 后，从 `start_addr` 起按地址**连续**取字节写入队列 `q`；不写 `len` 时一直读到**第一个没有数据的字节地址**就停；写了非负的 `len` 时，这一段里每个地址都必须有数据，否则判失败。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `filename` | input | `string` |  | memh 路径 |
| `q` | output | `bit [7:0] q[$]` |  | 输出字节队列 |
| `start_addr` | input | `bit [63:0]` |  | 起始字节地址 |
| `len` | input | `int` |  | 字节个数；省略表示连读直到遇到没有数据的地址 |

**返回值：** `bit` — 成功为 1，失败为 0。

## `write_memh_file`

把「字节地址到 8 位值」的存储写成 memh 文件。每行最多几个数据字节与同族 `memh_max_bytes_per_line` 字段一致，须在**重新生成**源码前在 `models.py` 中调整；生成后的函数签名不再携带该参数。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `filename` | input | `string` |  | 输出路径 |
| `src` | ref | `bit [7:0] src[bit [63:0]]` |  | 数据来源 |

**返回值：** `bit` — 成功为 1，失败为 0。

## `compare_memory`

比较两份「字节地址到 8 位值」的存储：出现过的地址集合须相同，同址字节须相等。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `actual` | ref | `bit [7:0] actual[bit [63:0]]` |  | 实际一侧 |
| `expected` | ref | `bit [7:0] expected[bit [63:0]]` |  | 期望一侧 |
| `expected_name` | input | `string` |  | 报错里称呼期望一侧用的名字 |

**返回值：** `bit` — 完全一致为 1，否则为 0。

## `compare_memh_file`

从 memh 文件读出期望数据，再与 `actual` 比较（规则同 `compare_memory`）。

| 参数 | 方向 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `actual` | ref | `bit [7:0] actual[bit [63:0]]` |  | 实际一侧 |
| `filename` | input | `string` |  | 期望 memh 路径 |

**返回值：** `bit` — 完全一致为 1，否则为 0。
