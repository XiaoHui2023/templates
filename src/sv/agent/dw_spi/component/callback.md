# Callback

`callback` 挂在 `dw_spi_sequencer` 上，用于注入软件片选行为和 DMA buffer 的 CPU 访问。默认硬件 CS 模式不调用片选 callback；只有 `SOFTWARE_CS` 才调用 `activate_chip_select()` / `release_chip_select()`。

寄存器配置不使用 callback，也不通过 sequencer 封装通用寄存器读写。需要配置控制器寄存器时，operation/core 直接使用大写 REG/FIELD 句柄。

## 注入方式

```systemverilog
class my_spi_cb extends dw_spi_callback;
    `uvm_object_utils(my_spi_cb)

    function new(string name="my_spi_cb");
        super.new(name);
    endfunction

    virtual task activate_chip_select(int cs_id);
        // drive CS active
    endtask

    virtual task release_chip_select(int cs_id);
        // drive CS inactive
    endtask

    virtual task cpu_read(input bit [63:0] addr, output bit [31:0] data, input uvm_path_e path);
        if (path == UVM_BACKDOOR)
            cpu_mem.peek32(addr, data);
        else
            cpu_bus.read32(addr, data);
    endtask

    virtual task cpu_write(input bit [63:0] addr, input bit [31:0] data, input uvm_path_e path);
        if (path == UVM_BACKDOOR)
            cpu_mem.poke32(addr, data);
        else
            cpu_bus.write32(addr, data);
    endtask
endclass

my_spi_cb cb = my_spi_cb::type_id::create("cb");
uvm_callbacks#(dw_spi_sequencer, dw_spi_callback)::add(sqr, cb);
```

## Chip Select

`activate_chip_select(int cs_id)` 在 `SOFTWARE_CS` 模式的一次 primitive transfer 开始前调用，让指定 CS 进入有效态。

`release_chip_select(int cs_id)` 在 `SOFTWARE_CS` 模式的一次 primitive transfer 结束后调用，释放指定 CS。

基类默认 `uvm_fatal`，要求软件 CS 环境必须 override。硬件 CS 使用 `SER`，不调用这些 callback。

## CPU Access

CPU callback 用于内置 DMA 的系统内存 buffer 访问，不用于控制器寄存器配置。

| Task | 参数 | 说明 |
| --- | --- | --- |
| `cpu_read` | `addr, data, path` | 从 `addr` 读取 32-bit little-endian word 到 `data`。 |
| `cpu_write` | `addr, data, path` | 向 `addr` 写入 32-bit little-endian word。 |

`path` 使用 `uvm_path_e`：

| Value | 用途 |
| --- | --- |
| `UVM_BACKDOOR` | DMA buffer 准备和回读。`dw_spi` 内置 DMA 当前固定使用这个路径。 |
| `UVM_FRONTDOOR` | 普通 CPU 总线访问。当前 `dw_spi` 没有通用 CPU 访问 operation，保留给用户扩展。 |

内置 DMA transfer 启动前，sequence 用 `cpu_write(addr, word, UVM_BACKDOOR)` 准备 AXI source buffer：写命令放 payload，读命令放 opcode/address 控制项。内置 DMA 读 transfer 完成后，sequence 用 `cpu_read(addr, word, UVM_BACKDOOR)` 回读同一 AXI buffer 中的 destination payload。

## External DMA

外部 DMA 配置生成 `start_external_dma(transfer_req)` 和 `finish_external_dma(transfer_req, read_data, ok)` callback。前者必须只完成 DMA engine 的配置与 arm 并返回，不能在 CS 尚未启动时阻塞等待完成；完整 `transfer_req` 提供 opcode、address、dummy、data、frame width 和方向，使 DMA 环境能维持同一个 CS window。后者等待 DMA engine 完成；read 返回来自 DUT 的实际字节，write 返回空队列并设置 `ok`。

外部 flash read 同时开启 `DMACR.TDMAE` 和 `RDMAE`：TX handshake 负责 command/address/dummy 控制阶段，RX handshake 负责 payload。外部 write/command-only transfer 开启 `TDMAE`。未 override 这两个 callback 时，基类会 `uvm_fatal`。
