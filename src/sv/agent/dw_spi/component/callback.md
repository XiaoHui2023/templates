# Callback

`callback` 挂在 `dw_spi_sequencer` 上，只承载环境相关行为。控制器寄存器仍由 operation/core 通过寄存器模型直接读写，不经过 callback。

## 生成开关

| Python 字段 | 默认值 | 生成内容 |
| --- | --- | --- |
| `software_cs` | `false` | `SOFTWARE_CS` 枚举、约束、`set_chip_select()` callback 和调用路径 |
| `byte_reorder` | `false` | `reorder_bytes()` callback 和 transfer 边界的数据转换路径 |
| `internal_dma` | `false` | `cpu_read()` / `cpu_write()` callback |
| `external_dma` | `false` | 外部 DMA start/finish callback |

关闭开关时，对应类型、方法和调用代码均不生成。

## 注入方式

```systemverilog
class my_spi_cb extends dw_spi_callback;
    `uvm_object_utils(my_spi_cb)

    function new(string name="my_spi_cb");
        super.new(name);
    endfunction

    virtual task set_chip_select(input int cs_id, input bit selected);
        cs_driver.set_selected(cs_id, selected);
    endtask

    virtual function void reorder_bytes(
            input bit [7:0] data[$],
            input bit is_read,
            output bit [7:0] reordered_data[$]);
        reordered_data = data;
        reordered_data.reverse();
    endfunction
endclass

my_spi_cb cb = my_spi_cb::type_id::create("cb");
uvm_callbacks#(dw_spi_sequencer, dw_spi_callback)::add(sqr, cb);
```

示例只展示同时开启 `software_cs` 和 `byte_reorder` 时的接口。实际生成结果由 Python 开关决定。

## Software CS

`set_chip_select(cs_id, selected)` 在一个 primitive transfer 的边界调用：`selected=1` 表示选中，`selected=0` 表示释放。`cs_id` 来自单次 transfer 配置包。

软件 CS 默认关闭。开启生成开关后，单次配置包仍默认约束为 `HARDWARE_CS`；用户显式选择 `SOFTWARE_CS` 时才调用 callback。软件 CS 仅支持 master 1x standard 路径。

基类实现会 `uvm_fatal`。sequencer 还会先检查 callback 列表；列表为空时同样 `uvm_fatal`，避免 UVM callback 宏在无注册对象时静默跳过。

## Byte Reorder

`reorder_bytes(data, is_read, reordered_data)` 的方向约定：

| `is_read` | 输入 | 输出用途 |
| --- | --- | --- |
| `0` | 用户/scoreboard 逻辑写入顺序 | 送往 PIO 或 DMA 的控制器传输顺序 |
| `1` | DUT 通过 DR0 或 DMA 返回的传输顺序 | flow 和 scoreboard 使用的逻辑读取顺序 |

默认基类直接执行 `reordered_data = data`，未注册 callback 时 sequencer 也保持透传。重排只能改变顺序，不能改变队列长度；长度变化会 `uvm_fatal`。

读取路径只重排有效 payload。`rx_skip_bytes` 指定的前导接收字节保持原样，由上层 flash flow 丢弃。写路径在传输结束前恢复 generic payload 的逻辑顺序，scoreboard 记录的也是逻辑数据，而不是线上的重排结果。

## CPU Access

CPU callback 用于内置 DMA 的系统内存 buffer 访问，不用于控制器寄存器配置。

| Task | 参数 | 说明 |
| --- | --- | --- |
| `cpu_read` | `addr, data, path` | 从 `addr` 读取 32-bit word 到 `data`。 |
| `cpu_write` | `addr, data, path` | 向 `addr` 写入 32-bit word。 |

`path` 使用 `uvm_path_e`。内置 DMA 当前使用 `UVM_BACKDOOR` 准备 source buffer 和回读 destination buffer；环境可在 override 中映射到 CPU/AXI memory model。

## External DMA

外部 DMA 配置生成 `start_external_dma(transfer_req)` 和 `finish_external_dma(transfer_req, read_data, ok)`。start 只负责配置并 arm DMA engine，不能在 CS 尚未启动时等待完成；finish 等待搬运完成并返回 DUT actual read bytes。未 override 时基类会 `uvm_fatal`。
