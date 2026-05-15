# 回调

类名与方法名均带配置的 `class_prefix` 前缀；下文只写类型与方法的 basename。

下面示例默认前缀为 **`memh_`**（与常见配置一致）；若你改了 `class_prefix`，请把类型名里的 **`memh_`** 换成你的前缀。

```systemverilog
class my_memh_cb extends memh_memh_io_callback;
  `uvm_object_utils(my_memh_cb)
  function new(string name="my_memh_cb");
    super.new(name);
  endfunction
  virtual function void on_write_data(bit [63:0] addr, const ref bit [7:0] data[$]);
    // 你的代码
  endfunction
endclass

// sqr：该 agent 里已创建的 sequencer 句柄（类型为 memh_sequencer）
my_memh_cb cb = my_memh_cb::type_id::create("memh_cb");
uvm_callbacks#(memh_sequencer, memh_memh_io_callback)::add(sqr, cb);
```

## `on_write_data`

在 **memory** 中一段连续字节写入完成后调用。从 **memh** 文件加载时，按文件内扫描得到的连续地址段分段触发，分段边界与按段写入 **memory** 一致。

| 方向 | 类型 | 参数名 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| input | `bit [63:0]` | `addr` | 无 | 本段首字节地址 |
| input | `const ref bit [7:0] data[$]` | `data` | 无 | 自 `addr` 起按地址递增排列的本段字节 |

## `on_clear`

在 **memory** 清空完成后调用。
