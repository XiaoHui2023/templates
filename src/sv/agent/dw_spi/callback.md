# 回调

`callback` 类型名前缀由 `class_prefix` 决定，与同前缀的 `sequencer` 配套使用。

callback 只用于注入片选行为。寄存器配置不走 callback，sequence 通过 sequencer 调用 `settings.regmodel.<reg>.write/read`。

```systemverilog
class my_spi_cb extends dw_spi_callback;
    `uvm_object_utils(my_spi_cb)

    function new(string name="my_spi_cb");
        super.new(name);
    endfunction

    virtual task assert_chip_select(dw_spi_transfer tr);
        // drive CS active
    endtask

    virtual task deassert_chip_select(dw_spi_transfer tr);
        // drive CS inactive
    endtask
endclass

my_spi_cb cb = my_spi_cb::type_id::create("cb");
uvm_callbacks#(dw_spi_sequencer, dw_spi_callback)::add(sqr, cb);
```

## `assert_chip_select`

一次 transfer 开始前调用。

| 方向 | 类型 | 参数名 | 说明 |
| --- | --- | --- | --- |
| input | `dw_spi_transfer` | `tr` | 当前传输 |

## `deassert_chip_select`

一次 transfer 结束后调用。

| 方向 | 类型 | 参数名 | 说明 |
| --- | --- | --- | --- |
| input | `dw_spi_transfer` | `tr` | 当前传输 |
