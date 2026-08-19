# Scoreboard

## Error Checks

- `check_actual_read()` can receive `expected_length`. A short, empty, or oversized DUT/DMA result reports `uvm_error` before byte comparison.
- Byte mismatches report the failing address, expected byte, actual byte, and comparison label.
- PIO actual read data comes from `DR0`; internal DMA actual read data comes from the CPU callback reading the AXI destination buffer; external DMA actual read data comes from `finish_external_dma()`.
- A successful write updates only the expected mirror. Write verification requires either observed bus data through `check_actual_write()` or a subsequent DUT readback. Never use the source payload as actual write data.

`scoreboard` 内部持有一个动态 byte queue 形式的 memory mirror，用来模拟 flash model 的有效数据区。sequence 把实际读写得到的数据交给 scoreboard，scoreboard 立即比较或更新 mirror。

## Memory

| 行为 | 说明 |
| --- | --- |
| 加载 | `load_memh()` 和 `load_hex()` 按文件内容扩展队列 |
| 写入 | `write_bytes()` 超过当前长度时自动扩展 |
| 读取 | 超过当前有效长度时报错 |
| 比较 | 逐 byte 比较，失败时报地址、model 值和 observed 值 |

不配置 flash size、page size、erase value。mirror 的长度由加载和写入行为自然决定。

## 文件加载

### `load_memh`

支持常见 memh token：

- `@addr` 修改写入地址。
- 十六进制数据 token 写入当前地址并递增。
- `//` 注释行跳过。

### `load_hex`

用于简单 `.hex` 文件。文件中所有有效十六进制字符都会按两个字符组成一个 byte，顺序写入 `base_addr` 开始的地址。

示例：

```text
aa
55
f4
```

会加载 3 个 byte：`8'haa`、`8'h55`、`8'hf4`。如果有效十六进制字符数量为奇数，加载失败。

## Payload

`apply_payload()` 消费 `uvm_tlm_generic_payload`：

1. 从 payload 读取 address、command、data length 和 byte data。
2. `UVM_TLM_WRITE_COMMAND` 写入 mirror。
3. `UVM_TLM_READ_COMMAND` 从 mirror 读取数据，写回 payload，并返回 `read_data`。
4. 其他 command 报错。

scoreboard 不消费协议专用 transfer 类，也不配置寄存器。

## 比较入口

| 函数 | 用途 |
| --- | --- |
| `record_expected_write()` | 记录期望写入数据 |
| `check_actual_read()` | 检查真实读回数据 |
| `check_actual_write()` | 检查真实写入数据 |
| `compare_actual()` | 通用逐 byte 比较 |

读写测试中，sequence 先写入，再读回，然后用 `check_actual_read(address, read_data, "rw_readback_actual", expected_length)` 检查 DUT 读回长度和数据是否与 mirror 一致。`read_data` 必须来自读传输从 `DR0` 或 DMA 目标 buffer 读回的 actual data，不能由 scoreboard 自己合成。
