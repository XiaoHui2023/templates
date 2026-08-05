# DW eMMC

## 示例

```yaml
card_type: emmc
class_prefix: Emmc_ctrl_
enable_dma: false

clock_defaults:
  crystal_frequence: 24000000
  tmclk_frequence: 1000000
  cqetmclk_frequence: 1000000
  tolerance: 5
  cclk_rx_relation_operator: "=="

monitored_clocks:
  - name: hclk
    enable: true
    check_type: presence
  - name: cclk_tx
    enable: true
    check_type: presence
  - name: cclk_rx
    enable: true
    check_type: relation
    relation_clock: cclk_tx
    relation_operator: "=="
  - name: tmclk
    enable: true
    check_type: frequency
    frequence: 1000000
```

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `card_type` | `emmc` / `sdcard` / `sdio` |  | 卡类型 |
| `class_prefix` | `str` | `Emmc_ctrl_` | 命名前缀 |
| `class_regmodel` | `str` | `ral_sys_DWC_mshc` | 寄存器模型类名 |
| `class_regmodel_rm` | `str` | `ral_block_DWC_mshc_map_DWC_mshc_block` | 标准寄存器块类名 |
| `class_regmodel_rm_vd1` | `str` | `ral_block_DWC_mshc_map_DWC_mshc_vendor1_block` | vendor1 寄存器块类名 |
| `clock_defaults` | `ClockDefaults` |  | 时钟默认值 |
| `monitored_clocks` | `list[MonitoredClock]` |  | 时钟检查配置 |
| `enable_dma` | `bool` | `false` | 内置 DMA |

### ClockDefaults

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `crystal_frequence` | `int` | `24000000` | 晶振频率 |
| `tmclk_frequence` | `int` | `1000000` | `tmclk` 默认频率 |
| `cqetmclk_frequence` | `int` | `1000000` | `cqetmclk` 默认频率 |
| `tolerance` | `int` | `5` | 频率容差 |
| `cclk_rx_relation_operator` | `>` / `>=` / `<` / `<=` / `==` | `==` | `cclk_rx` 与 `cclk_tx` 默认关系 |

### MonitoredClock

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `name` | `str` |  | 时钟名 |
| `enable` | `bool` | `false` | 是否检查 |
| `check_type` | `presence` / `relation` / `frequency` |  | 检查类型 |
| `frequence` | `int` | `0` | 固定频率 |
| `min_frequence` | `int` | `24000000` | 有时钟的最小频率 |
| `tolerance` | `int` | `5` | 频率容差 |
| `relation_clock` | `str` |  | 大小关系目标时钟 |
| `relation_operator` | `>` / `>=` / `<` / `<=` / `==` | `==` | 大小关系 |

#### check_type

| 取值 | 配置 |
| --- | --- |
| `presence` | `min_frequence` |
| `relation` | `relation_clock`、`relation_operator`、`tolerance` |
| `frequency` | `frequence`、`tolerance` |

### 内置时钟

| 时钟 | 默认检查 | 默认类型 |
| --- | :---: | --- |
| `hclk` | ✓ | `presence` |
| `aclk` |  | `presence` |
| `cclk_tx` |  | `presence` |
| `cclk_rx` |  | `relation` |
| `tmclk` |  | `frequency` |
| `cqetmclk` |  | `frequency` |

`sdcard` 和 `sdio` 不使用 `cqetmclk`。`monitored_clocks` 里写同名时钟表示覆盖内置值；写新名字表示新增时钟。

示例按默认 `class_prefix: Emmc_ctrl_` 书写；改过前缀时，只替换类名前缀。

## 例化

```systemverilog
Emmc_ctrl_interface emmc_if(
    .hclk(hclk),
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
    // env.emmc_agent.sqr.power_up_operation(1); // 主动执行 power up 软复位
    env.emmc_agent.sqr.switch_bus(HS400, 8);
    env.emmc_agent.sqr.rw_test(.addr('h0), .count(2));
    env.emmc_agent.sqr.speed_mode_test(.enable_hs200_4bit(1), .enable_hs400_8bit(1));

    phase.drop_objection(this);
endtask
```

`initial_card()` 完成初始化流程；`switch_bus()` 执行切总线 flow；`rw_test()` 按地址先写后读。Python 配置 `enable_dma: true` 后，`rw_test()` 额外生成 `use_dma` 参数，`use_dma = 1` 时使用内置 DMA 搬运。kit sequencer 还提供 `frequence_set_operation()`、`power_up_operation()`、`reset_operation()`、`reg_test()`、`speed_mode_test()`、`tune_test()`、`check_clock_frequence_test()`。
