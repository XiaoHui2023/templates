# 回调

展开类型名带 **class_prefix** 前缀；在 **agent** 的 **sqr** 上注册派生 **callback**。**uvm_register_cb** 挂在 **sequencer** 类型上。

## 示例

下例中 **`your_prefix_*`** 须换成本地 **class_prefix** 拼出的类型名；**`sqr`** 为 **kit_sequencer** 句柄，**callback** 仍注册在 **sequencer** 类型上。

```systemverilog
class your_prefix_my_cb extends your_prefix_callback;
  `uvm_object_utils(your_prefix_my_cb)
  function new(string name="your_prefix_my_cb");
    super.new(name);
  endfunction
  virtual function void on_apply_settings(your_prefix_settings settings);
    // 按 settings 字段写寄存器或系统配置
  endfunction
endclass

your_prefix_my_cb cb = your_prefix_my_cb::type_id::create("clk_tree_cb");
uvm_callbacks#(your_prefix_sequencer, your_prefix_callback)::add(sqr, cb);
```

## `on_apply_settings`

按 **settings** 字段完成系统配置，如写寄存器或时钟相关设置；配置完成后对已绑定的各 **tree** 做时钟树检查。对 **`sqr.apply_settings`** 时调用；**settings** 实参为空时对 **trees** 中每棵 **tree** 的 **settings** 各调用一次。

| 方向 | 类型 | 参数名 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| input | settings | settings | 无 | 当前要写入的设置实例，通常来自 **`tree.settings`** |
