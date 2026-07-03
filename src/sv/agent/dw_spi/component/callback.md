# callback

`callback` 挂在 `dw_spi_sequencer` 上，只用于注入片选行为。

寄存器配置不使用 callback，也不通过 sequencer 封装通用读写。需要配置寄存器时，operation/core 直接使用大写 REG/FIELD 句柄，例如 `settings.regmodel.CTRLR0.write/read`。

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
