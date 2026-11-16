# Scoreboard

类型名使用配置的 `class_prefix`，示例使用 `general_`。

## 输入

两个端口的载荷均为 `uvm_tlm_generic_payload`。不接受用户数据类型配置，不比较 GP 扩展、自定义字段或 DMI。

| 端口 | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| `i_golden_ap` | 输入 | `uvm_tlm_generic_payload` | 准确的期望数据。 |
| `i_monitor_ap` | 输入 | `uvm_tlm_generic_payload` | 实际采样数据，可包含无关地址。 |

```systemverilog
golden_producer.o_ap.connect(sb.i_golden_ap);
monitor.o_ap.connect(sb.i_monitor_ap);
```

## 运行配置

在首次输入之前调用 `configure`。配置会被复制，修改原配置对象不会影响当前比较；已有输入后再次配置会中止。也可通过 `uvm_config_db` 的 `config` 设置 `general_config` 对象。

```systemverilog
general_config options;
options = new;
options.mode = general_config::ADDRESS;
options.atomize = 1;
options.monitor_policy = general_config::DROP;
sb.configure(options);
```

### 地址匹配

`ADDRESS` 在不同地址之间允许乱序，同一匹配条件按到达顺序一一比较。地址与命令是否参与匹配由 `match_address`、`match_command` 决定。匹配后才按 `compare_*` 核对内容；匹配到的错误数据会报错。

默认按地址匹配并比较命令。若命令也用作匹配条件，无关命令可以被过滤。无法仅凭地址区分的同址数据，需要选用命令条件或使用多重集合模式。

### 多重集合

`SET` 在相同匹配条件下寻找内容相等的候选并逐个消耗。不同值可乱序，重复值按次数比较。暂时找不到相等候选时保存数据，结束时检查缺失及多余次数。

### 顺序比较

`ORDERED` 按两条输入流的全局顺序一一比较，忽略 `match_*` 的挑选条件；`compare_*` 仍生效。此模式要求输入流已经过滤无关数据。

## monitor 过滤

`DROP` 只接收已经由 golden 登记的匹配条件。golden 应在对应 monitor 之前发送。登记一直保留至复位，同址多余次数不会作为噪声丢弃。

`BUFFER` 允许 monitor 先到，结束时忽略从未被 golden 登记的残留数据；已登记条件的残留仍报错。`STRICT` 对全部残留报错。

两条流的待匹配单元、历史匹配条件和单包长度分别受容量配置限制。超过上限中止，缓存不会自动淘汰或覆盖旧数据。

## GP 数据

有效长度必须与 `set_data_length`、`set_byte_enable_length` 分别设置，且不得超过数组容量。短字节使能按周期重复，00 为禁用，ff 为有效。IGNORE 与完全禁用的数据不参与比较。

`atomize` 为真时，每个有效字节按地址比较，可比较不同的分包方式；地址为起始地址加字节序号对有效 streaming width 的余数。width 为 0 或大于等于长度时按连续地址处理。数据顺序保持 GP 数组顺序。

整包模式同时核对有效长度、有效 streaming width，以及选择的字段。两份 GP 的有效位置必须一致，禁用位置的数据值被忽略。

```systemverilog
uvm_tlm_generic_payload payload;
byte unsigned bytes_[];
payload = new("payload");
bytes_ = new[2];
bytes_[0] = 8'h12;
bytes_[1] = 8'h34;
payload.set_write();
payload.set_address(64'h1000);
payload.set_data(bytes_);
payload.set_data_length(2);
payload.set_streaming_width(0);
```

## 检查与复位

`check_phase` 自动检查未消耗数据。可调用 `check_pending` 提前检查；没有新输入时重复调用不重复报告。此函数检查当前状态，报告出的错误不会因后续匹配而撤销。

`reset_phase` 自动执行 `clear`，也可在测试中显式调用 `clear` 开始新一轮比较。此操作丢弃待匹配数据、历史地址及计数，允许重新配置，不会清除 UVM 已记录的错误。复位期间的生产者应自行停止输入。

`pending_counts` 返回 golden 与 monitor 的待匹配单元数。`matched_count` 记录成功配对数，`mismatched_count` 记录立即比较失败数，`dropped_count` 记录过滤数。逐字节模式按字节计数，整包模式按包计数；最终结论还须检查 UVM 的缺失与多余数据错误。

## 包打印

`print_payload` 使用 GP 的标准行打印器，以一条 `UVM_INFO` 输出内容，支持报告 ID 与 verbosity。比较失败的两份 GP 也通过此接口打印。没有表格、文件报告、成功汇总或逐项历史记录；输入、比较、缺失、多余数据和容量错误保留 UVM 的错误级别。

```systemverilog
sb.print_payload(payload, "GP_DEBUG", UVM_HIGH);
```
