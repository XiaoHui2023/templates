# callback

`callback` 挂在 `dw_spi_sequencer` 上，用于注入片选行为和 DMA buffer 的 CPU 访问。

寄存器配置不使用 callback，也不通过 sequencer 封装通用寄存器读写。需要配置寄存器时，operation/core 直接使用大写 REG/FIELD 句柄，设置 FIELD 后由所属 REG `read/write`。

## 注入方式

```systemverilog
class my_spi_cb extends dw_spi_callback;
    `uvm_object_utils(my_spi_cb)

    function new(string name="my_spi_cb");
        super.new(name);
    endfunction

    virtual task activate_chip_select(int unsigned cs_id);
        // drive CS active
    endtask

    virtual task release_chip_select(int unsigned cs_id);
        // drive CS inactive
    endtask

    virtual task cpu_read(bit [63:0] addr, output bit [31:0] data);
        cpu_bus.read32(addr, data);
    endtask

    virtual task cpu_write(bit [63:0] addr, bit [31:0] data);
        cpu_bus.write32(addr, data);
    endtask
endclass

my_spi_cb cb = my_spi_cb::type_id::create("cb");
uvm_callbacks#(dw_spi_sequencer, dw_spi_callback)::add(sqr, cb);
```

## `activate_chip_select`

一次 primitive transfer 开始前调用，让指定 CS 进入有效态。具体电平极性由 callback 实现决定。

| 方向 | 类型 | 参数名 | 说明 |
| --- | --- | --- | --- |
| input | `int unsigned` | `cs_id` | 片选号 |

## `release_chip_select`

一次 primitive transfer 结束后调用，释放指定 CS。具体电平极性由 callback 实现决定。

| 方向 | 类型 | 参数名 | 说明 |
| --- | --- | --- | --- |
| input | `int unsigned` | `cs_id` | 片选号 |

## `cpu_read`

内部 DMA 读传输完成后调用，从 `axi_addr` 指定的系统内存 buffer 读取 32-bit word，再由 sequence 拆成 byte 队列作为 actual read data。

| 方向 | 类型 | 参数名 | 说明 |
| --- | --- | --- | --- |
| input | `bit [63:0]` | `addr` | CPU/AXI byte 地址 |
| output | `bit [31:0]` | `data` | 32-bit little-endian word |

## `cpu_write`

内部 DMA 写传输启动前调用，把 payload byte 按 32-bit word 写入 `axi_addr` 指定的系统内存 buffer，供控制器 DMA 搬运。

| 方向 | 类型 | 参数名 | 说明 |
| --- | --- | --- | --- |
| input | `bit [63:0]` | `addr` | CPU/AXI byte 地址 |
| input | `bit [31:0]` | `data` | 32-bit little-endian word |
