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

## 本轮边界

`end_golden` 表示本轮期望数据已全部提交；`end_monitor` 表示本轮实际采样已全部提交。**两个结束标记都存在，才允许判定完成。** 两个接口均可重复调用。协调方确认两条输入流已经停止后，可调用 `end_round` 同时标记结束。

输入暂空、数量满足或一段时间没有数据，都不代表生产者已经结束。`wait_complete` 不会根据这些现象自动关闭输入，也不会用超时作为成功边界。关闭后再次提交对应输入会记录轮次错误，并使此前的成功状态失效；`check_phase` 仍会检查这种晚到输入。

结束标记应由掌握生产者进度的代码发出。golden 序列结束不代表 monitor 已经排空 DUT 的输出；monitor 的结束标记应在实际采样结束后提交。

## 预期比较单元数

`set_expected_units` 设置本轮总数，`add_expected_units` 追加数量。参数为非负 `longint`；负数、追加溢出以及 `end_golden` 后修改数量都报错。golden 关闭前可分批追加，达到当前声明数量不会提前完成。

没有显式声明数量时，`end_golden` 会将已经提交的 golden 比较单元总数作为本轮预期数。显式声明时，最终同时核对 golden 提交单元数与实际比较单元数。

比较单元随模式变化：逐有效字节模式每个有效字节为一个单元，整包模式每个参与比较的 GP 为一个单元。包数、有效字节数和比较单元数分别统计，预期数量接口只使用比较单元。

```systemverilog
sb.set_expected_units(4);
// Submit the first batch.
sb.add_expected_units(2);
// Submit the remaining golden data, then close that producer.
sb.end_golden();
// Close monitor only after all its sampling has finished.
sb.end_monitor();
```

## 完成等待与最终检查

```systemverilog
general_scoreboard::completion_e result;
// Numeric nanoseconds; do not pass a time literal to timeout_ns.
sb.wait_complete(result, 1000.0);
if (result != general_scoreboard::COMPLETE)
    `uvm_error("SB_DONE", "scoreboard round did not complete successfully")
```

`timeout_ns` 是整次调用的数值纳秒预算，0 为无限等待；正数向上量化至 1fs。输入到达不会延长预算。时间服务具有独立的 1fs 时间范围，无须改变调用者的时间单位；服务会参与全局最小仿真精度的计算。64 位 fs 时间范围内的负数、非有限值与期限溢出会被拒绝。边界提交与到期在同一仿真时刻发生时，处理先后由调度顺序决定。

| 返回值 | 含义 |
| --- | --- |
| `COMPLETE` | 双边已结束，非空策略、失配、预期数量和相关残留全部通过。 |
| `FAILED` | 已检测到本轮错误，或关闭后最终检查失败。 |
| `TIMED_OUT` | 本次等待超过预算；超时记入本轮失败。 |
| `RESET` | 等待期间发生 `clear` 或复位，原轮次被取消。 |

`require_golden` 检查至少收到一包合法 golden 输入，IGNORE 和完全禁用的数据也属于合法输入包；`require_match` 检查至少有一个比较单元成功匹配。两项独立配置且默认打开。显式允许空轮次时须关闭两项，仍须提交双边结束标记。

`is_complete` 是不打印的当前状态查询。`check_round` 执行完整最终检查，`check_phase` 自动调用它，无须项目重载。`check_pending` 保留为仅检查当前残留的接口，不能证明本轮已结束。没有状态变化时重复检查不会重复报告。已报告的错误保持到本轮清理；后续数据恢复匹配不能撤销它。

等待接口不会自动管理 phase objection；调用者应在等待期间保持运行 phase。

## 统计快照

`get_statistics` 返回独立对象，修改快照不会改变 scoreboard；快照也不会随之后的输入变化。统计只供查询，不自动输出汇总。

```systemverilog
general_statistics stats;
sb.get_statistics(stats);
```

| 字段 | 单位与含义 |
| --- | --- |
| `round_id` | 轮次编号，每次清理递增。 |
| `golden_packets`、`monitor_packets` | 合法输入 GP 包数，包含 IGNORE 与完全禁用的包。 |
| `golden_valid_bytes`、`monitor_valid_bytes` | 参与比较的有效字节数，排除禁用字节，IGNORE 为零。 |
| `golden_units`、`monitor_units` | 转换所得比较单元数；monitor 包含随后被过滤的单元。 |
| `compared_units` | 已配对并执行比较的单元数，等于成功数加失配数。 |
| `matched_count`、`mismatched_count` | 成功与立即失配的比较单元数；SET 无相等候选时保留为残留。 |
| `dropped_count` | 按过滤策略丢弃的比较单元数。 |
| `pending_golden`、`pending_monitor` | 当前未消耗的比较单元数。 |
| `unexpected_monitor` | 按当前过滤策略必须检查的 monitor 残留单元数。 |
| `expected_units`、`expected_set` | 已知预期比较单元数及有效标记。 |
| `input_errors`、`protocol_errors` | 输入校验错误与轮次 API 或容量错误次数。 |
| `timeout_count`、`check_errors` | 等待超时次数与最终检查错误项数。 |
| `golden_closed`、`monitor_closed` | 两条输入流的结束标记。 |
| `failed`、`complete` | 当前轮次的失败与完成状态。 |

## 清理与复位

`clear` 同步清空待匹配数据、历史身份、全部统计、预期数量、结束标记和本轮错误状态，并允许重新配置。轮次编号递增，旧等待者返回 `RESET`，不会继续等待下一轮或污染下一轮的统计。`reset_phase` 自动调用同一接口。

清理不清除 UVM 全局已记录的错误。生产者应在清理期间停止提交；GP 不携带轮次号，清理后到达的数据会被视为新一轮输入。

## 包打印

`print_payload` 使用 GP 的标准行打印器，以一条 `UVM_INFO` 输出内容，支持报告 ID 与 verbosity。比较失败的两份 GP 也通过此接口打印。没有表格、文件报告、成功汇总或逐项历史记录；输入、比较、缺失、多余数据和容量错误保留 UVM 的错误级别。

```systemverilog
sb.print_payload(payload, "GP_DEBUG", UVM_HIGH);
```
