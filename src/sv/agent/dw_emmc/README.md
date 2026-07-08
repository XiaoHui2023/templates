# DW eMMC

示例按默认 `class_prefix: Emmc_ctrl_` 书写；改过前缀时，只替换类名前缀。

## 例化

```systemverilog
Emmc_ctrl_interface emmc_if(
    .aclk(aclk),
    .hclk(hclk),
    .cclk_tx(cclk_tx),
    .cclk_rx(cclk_rx),
    .tmclk(tmclk),
    .cqetmclk(cqetmclk),
    .intr(intr),
    .heartbeat(heartbeat)
);
```

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
env.emmc_agent.settings.chk_clk_cfg.should = 1;
```

## Callback

```systemverilog
class tb_emmc_callback extends Emmc_ctrl_callback;
    `uvm_object_utils(tb_emmc_callback)

    function new(string name = "tb_emmc_callback");
        super.new(name);
    endfunction

    task set_frequence(Emmc_ctrl_sequencer sqr, int frequence, ref bit handled);
        clock_ctrl.set_cclk(frequence);
        handled = 1;
    endtask

    task cpu_read(
        Emmc_ctrl_sequencer sqr,
        bit[63:0] addr,
        uvm_path_e path,
        output bit[31:0] data,
        ref bit handled
    );
        cpu_bus.read32(addr, data, path);
        handled = 1;
    endtask

    task cpu_write(
        Emmc_ctrl_sequencer sqr,
        bit[63:0] addr,
        bit[31:0] data,
        uvm_path_e path,
        ref bit handled
    );
        cpu_bus.write32(addr, data, path);
        handled = 1;
    endtask
endclass
```

```systemverilog
tb_emmc_callback cb;

cb = tb_emmc_callback::type_id::create("cb");
uvm_callbacks#(Emmc_ctrl_sequencer, Emmc_ctrl_callback)::add(env.emmc_agent.sqr, cb);
```

调频、CPU 读、CPU 写都走 callback；没有 callback 或 callback 未置 `handled = 1` 时会直接 `uvm_fatal`。

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
    env.emmc_agent.sqr.rw(.addr('h0), .count(2), .use_dma(0));
    env.emmc_agent.sqr.rw(.addr('h1000), .count(2), .use_dma(1));
    env.emmc_agent.sqr.run_speed_mode_test();

    phase.drop_objection(this);
endtask
```

`initial_card()` 完成初始化流程；`switch_bus()` 执行切总线 flow；`rw()` 按地址先写后读，`use_dma = 1` 时走内置 DMA 搬运。kit sequencer 还提供 `run_frequence_set_operation()`、`run_power_up_operation()`、`run_reset_operation()`、`run_reg_test()`、`run_speed_mode_test()`、`run_sram_test()`、`run_tune_test()`、`run_check_clock_frequence_test()`。
