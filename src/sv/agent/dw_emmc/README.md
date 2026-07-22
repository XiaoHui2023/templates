# DW eMMC

示例按默认 `class_prefix: Emmc_ctrl_` 书写；改过前缀时，只替换类名前缀。

## 例化

```systemverilog
Emmc_ctrl_interface emmc_if(
    .hclk(hclk),
    .intr(intr),
    .heartbeat(heartbeat)
);
```

默认只生成 `hclk` 时钟端口。需要检查其它 clock 时，在 Python 输入 `monitored_clocks` 中把对应 clock 设为 `enable: true`，端口和检查代码才会生成。内置 clock 默认值通过 Python 输入 `clock_defaults` 配置。

```systemverilog
class env extends uvm_env;
    Emmc_ctrl_agent emmc_agent;

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);

        emmc_agent = Emmc_ctrl_agent::type_id::create("emmc_agent", this);
        emmc_agent.settings.vif = tb_top.emmc_if;
        emmc_agent.settings.regmodel = rm;
    endfunction
endclass
```

## Settings

`agent` 在 `new()` 中创建 `settings`。`vif` 和 `regmodel` 必须给；`boot_cfg`、`chk_clk_cfg` 按用例需要约束或直接赋值。

```systemverilog
env.emmc_agent.settings.boot_cfg.default_data_width = DATA_WIDTH_8;
env.emmc_agent.settings.boot_cfg.default_bus_speed_mode = HS400;
env.emmc_agent.settings.chk_clk_cfg.min_frequence_hclk = 24000000;
```

## Callback

```systemverilog
class tb_emmc_callback extends Emmc_ctrl_callback;
    `uvm_object_utils(tb_emmc_callback)

    function new(string name = "tb_emmc_callback");
        super.new(name);
    endfunction

    task set_frequence(int frequence);
        clock_ctrl.set_cclk(frequence);
    endtask

    task cpu_read(
        input bit[63:0] addr,
        output bit[31:0] data,
        input uvm_path_e path
    );
        if(path == UVM_BACKDOOR)
            mem_backdoor.read32(addr, data);
        else
            cpu_bus.read32(addr, data);
    endtask

    task cpu_write(
        input bit[63:0] addr,
        input bit[31:0] data,
        input uvm_path_e path
    );
        if(path == UVM_BACKDOOR)
            mem_backdoor.write32(addr, data);
        else
            cpu_bus.write32(addr, data);
    endtask
endclass
```

```systemverilog
tb_emmc_callback cb;

cb = tb_emmc_callback::type_id::create("cb");
uvm_callbacks#(Emmc_ctrl_sequencer, Emmc_ctrl_callback)::add(env.emmc_agent.sqr, cb);
```

调频、CPU 读、CPU 写都通过 callback。CPU callback 传地址、32-bit word 和 `path`；`UVM_FRONTDOOR` 用于普通 CPU 访问。Python 配置 `enable_dma: true` 后，DMA buffer 和 ADMA descriptor 准备/回读使用 `UVM_BACKDOOR`。

## Scoreboard

```systemverilog
void'(env.emmc_agent.scb.load_memh("card_init.memh", 'h0));
void'(env.emmc_agent.scb.load_hex("card_init.hex", 'h0));
```

二选一加载初始镜像。写流程发送 payload 更新 scoreboard 期望值，读流程发送 payload，由 scoreboard 用自己的 memory 比较实际读回数据。

## 启动

```systemverilog
task run_phase(uvm_phase phase);
    phase.raise_objection(this);

    env.emmc_agent.sqr.initial_card();
    env.emmc_agent.sqr.switch_bus(HS400, 8);
    env.emmc_agent.sqr.rw_test(.addr('h0), .count(2));
    env.emmc_agent.sqr.speed_mode_test(.enable_hs200_4bit(1), .enable_hs400_8bit(1));

    phase.drop_objection(this);
endtask
```

`initial_card()` 完成初始化流程；`switch_bus()` 执行切总线 flow；`rw_test()` 按地址先写后读。Python 配置 `enable_dma: true` 后，`rw_test()` 额外生成 `use_dma` 参数，`use_dma = 1` 时使用内置 DMA 搬运。kit sequencer 还提供 `frequence_set_operation()`、`power_up_operation()`、`reset_operation()`、`reg_test()`、`speed_mode_test()`、`tune_test()`、`check_clock_frequence_test()`。
