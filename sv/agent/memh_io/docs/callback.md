# 回调

## 示例

下例中 **`your_prefix_*`** 须换成本地 **`class_prefix`** 拼出的类型名；**`sqr`** 为 **sequencer** 句柄。

```systemverilog
class your_prefix_my_cb extends your_prefix_callback;
  `uvm_object_utils(your_prefix_my_cb)
  function new(string name="your_prefix_my_cb");
    super.new(name);
  endfunction
  virtual function void on_write_data(bit [63:0] addr, const ref bit [7:0] data[$]);
    // …
  endfunction
  virtual function void after_read_data(input bit [63:0] addr, input int len, ref bit [7:0] data[$]);
    // …
  endfunction
endclass

your_prefix_my_cb cb = your_prefix_my_cb::type_id::create("memh_cb");
uvm_callbacks#(your_prefix_sequencer, your_prefix_callback)::add(sqr, cb);
```

## `on_write_data`

**memory** 里一段连续字节写完后调用 **`on_write_data`**。

- **会触发**
  - `write_byte`、`write_data`、`write_payload` 写完 **memory** 后；`imp` 上的 `write` 最终仍调用 `write_payload`
  - `load_file` 合并进 **memory** 时：memh 里每个连续地址区间在全部写入 **memory** 后调用 **`on_write_data`** 一次；区间内逐字节写入不单独调用 **`on_write_data`**
- **不会触发**
  - 仅 `mem_store_byte` 改 **memory**、未触发 `on_write_data` 时
  - `load_file` 且 `clear_first` 时开头的 **memory** 清空：不调用 **`on_clear`**，也不单独调用 **`on_write_data`**；随后合并写入再按区间调用 **`on_write_data`**

| 方向 | 类型 | 参数名 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| input | `bit [63:0]` | `addr` | 无 | 首字节地址 |
| input | `const ref bit [7:0] data[$]` | `data` | 无 | 字节 |

## `on_clear`

**memory** 被清空后调用 **`on_clear`**。

- **会触发**
  - 调用 `clear` 之后
- **不会触发**
  - `load_file` 且 `clear_first` 为真时直接 `memory.delete()` 的那一步，未调用 `clear`

## `after_read_data`

读路径把 **memory** 填进字节队列后调用 **`after_read_data`**；只可改元素值，不得增删条目；进入与返回时队列长度须与长度形参一致。

- **会触发**
  - 每次 `read_byte`
  - 每次 `read_data`，且长度大于零时整段一次
  - `compare_file`、`compare_memory` 从 **memory** 按连续地址区间读时：每区间一次，内部调用 `read_data`
- **不会触发**
  - `read_data` 长度为零
  - `save_file` 从 **memory** 直读写文件，不通过 `read_byte` / `read_data`
  - 只改 **memory** 且未通过上述读 API，例如外部下标写或仅用写类 API
  - `load_file` 只写 **memory**、不通过 **memory** 的读接口；期望 memh 在 **`load_file`** 中由 **`engine`** 从文件读入，与 **memory** 无关

| 方向 | 类型 | 参数名 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| input | `bit [63:0]` | `addr` | 无 | 首字节地址 |
| input | `int` | `len` | 无 | 区间字节个数 |
| ref | `bit [7:0] data[$]` | `data` | 无 | 字节队列 |
