# Scoreboard

类型名由 `class_prefix` 和固定的组件名称组成。示例前缀为 `general_`，主组件为 `general_scoreboard`，辅助类型均带 `scoreboard_`。前缀按原文拼接，不会自动补下划线或删除已有词语。

| 角色 | 示例类型名 |
| --- | --- |
| 主组件 | `general_scoreboard` |
| 配置 | `general_scoreboard_config` |
| 统计快照 | `general_scoreboard_statistics` |
| GP 转换与比较 | `general_scoreboard_adapter` |
| 内部期望记录 | `general_scoreboard_entry` |
| 内部待匹配存储 | `general_scoreboard_pending` |
| 时间服务包 | `general_scoreboard_time_domain` |

旧的 `general_config`、`general_statistics` 等辅助类型需迁移到上述名称；没有保留旧名别名。主组件、`i_golden_ap`、`i_monitor_ap` 和配置键 `config` 保持原名。

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

在首次输入之前调用 `configure`。配置会被复制，修改原配置对象不会影响当前比较；已有输入后再次配置会中止。也可通过 `uvm_config_db` 的 `config` 设置 `general_scoreboard_config` 对象。

```systemverilog
general_scoreboard_config options;
options = new;
options.mode = general_scoreboard_config::ADDRESS;
options.atomize = 1;
options.monitor_policy = general_scoreboard_config::DROP;
sb.configure(options);
```

### 地址匹配

`ADDRESS` 在不同地址之间允许乱序，同一匹配条件按到达顺序一一比较。地址与命令是否参与匹配由 `match_address`、`match_command` 决定。匹配后才按 `compare_*` 比较内容；匹配到的错误数据会报错。

默认按地址匹配并比较命令。若命令也用作匹配条件，无关命令可以被过滤。无法仅凭地址区分的同址数据，需要选用命令条件或使用多重集合模式。

### 多重集合

`SET` 在相同匹配条件下寻找内容相等的候选并逐个消耗。不同值可乱序，重复值按次数比较。暂时找不到相等候选时保存数据，结束时检查缺失及多余次数。

### 顺序比较

`ORDERED` 按两条输入流的全局顺序一一比较，忽略 `match_*` 的挑选条件；`compare_*` 仍生效。此模式要求输入流已经过滤无关数据。

## 读期望复用

`reuse_read_expectations` 为真时，读期望保留到本轮清理；每次相关读采样都重新比较。已覆盖的读期望仍参与比较，不会把重复读去重或丢弃。写期望始终逐个消费，多出来的写采样仍按残留数据检查。

```systemverilog
general_scoreboard_config options;
options = new;
options.reuse_read_expectations = 1;
sb.configure(options);
```

读样本在 `end_golden` 确定全部期望后逐条处理，此前按缓存容量保存。这样 monitor 先到、同址多个期望或相同内容多次声明时，都不会因提前复用第一条而失去覆盖后续期望的机会。通常应提交完整 golden 并调用 `end_golden`，再开始大量采样；提前到达的样本仍受 `max_pending` 限制。

ADDRESS 和 SET 对同一身份的读候选优先选择尚未覆盖且内容相等的期望，再复用已经覆盖的相等期望；没有相等候选时仍选取相关读期望执行失配比较。多个相同的 golden 是多个独立期望，必需分别首次覆盖。

ORDERED 仍保持首次覆盖及写操作的顺序，已经覆盖的读允许穿插复读；尚未覆盖的后续读不能跨越前置写。启用复用时，读写命令始终区分，即使关闭 `match_command` 或 `compare_command` 也不会用读期望满足写采样。

`compared_units` 记录每次实际比较，包括复读及失配；`covered_units` 仅在某条期望第一次成功比较时增加。覆盖全部期望后仍需等本轮 monitor 明确结束；结束前的每次复读仍会比较，任一次错误都会使本轮失败。

关闭此配置时读写都恢复为一对一消费。匹配、覆盖、数量检查和复位全部由模板内部处理，不需要派生 scoreboard 或覆写方法。

## monitor 过滤

`DROP` 只接收已经由 golden 登记的匹配条件。golden 应在对应 monitor 之前发送。登记一直保留至复位，同址多余次数不会作为噪声丢弃。

`BUFFER` 允许 monitor 先到，结束时忽略从未被 golden 登记的残留数据；已登记条件的残留仍报错。`STRICT` 对全部残留报错。

两条流的待匹配单元、历史匹配条件和单包长度分别受容量配置限制。超过上限中止，缓存不会自动淘汰或覆盖旧数据。

## GP 数据

有效长度必需与 `set_data_length`、`set_byte_enable_length` 分别设置，且不得超过数组容量。短字节使能按周期重复，00 为禁用，ff 为有效。IGNORE 与完全禁用的数据不参与比较。

`atomize` 为真时，每个有效字节按地址比较，可比较不同的分包方式；地址为起始地址加字节序号对有效 streaming width 的余数。width 为 0 或大于等于长度时按连续地址处理。数据顺序保持 GP 数组顺序。

整包模式同时比较有效长度、有效 streaming width，以及选择的字段。两份 GP 的有效位置必需一致，禁用位置的数据值被忽略。

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

没有显式声明数量时，`end_golden` 会将已经提交的 golden 比较单元总数作为本轮预期数。显式声明时自动停用两项非空兜底，最终同时比较 golden 提交单元数与成功覆盖的期望单元数；比较次数可因复读大于预期数量。

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

`timeout_ns` 是整次调用的数值纳秒预算，0 为无限等待；正数向上量化至 1fs。输入到达不会延长预算。时间服务具有独立的 1fs 时间范围，不需要改变调用者的时间单位；服务会参与全局最小仿真精度的计算。64 位 fs 时间范围内的负数、非有限值与期限溢出会被拒绝。边界提交与到期在同一仿真时刻发生时，处理先后由调度顺序决定。

| 返回值 | 含义 |
| --- | --- |
| `COMPLETE` | 双边已结束，非空策略、失配、预期数量和相关残留全部通过。 |
| `FAILED` | 已检测到本轮错误，或关闭后最终检查失败。 |
| `TIMED_OUT` | 本次等待超过预算；超时记入本轮失败。 |
| `RESET` | 等待期间发生 `clear` 或复位，原轮次被取消。 |

`require_golden` 检查至少收到一包合法 golden 输入，IGNORE 和完全禁用的数据也属于合法输入包；`require_match` 检查至少有一个比较单元成功匹配。两项独立配置且默认打开，仅在本轮没有成功调用 `set_expected_units` 或 `add_expected_units` 时兜底。显式设置数量后，两项自动停用，配置对象中的原值不变；包括显式设置 0 或追加 0。显式 0 允许空轮次，仍需双边结束、无错误且无相关残留。未显式设置时，即使关闭 golden 后推导出数量为 0，两项兜底仍按配置执行。负数、溢出或关闭后被拒绝的设置不会改变数量来源。

`is_complete` 是不打印的当前状态查询。`check_round` 执行完整最终检查，`check_phase` 自动调用它，不需要项目重载。`check_pending` 保留为仅检查当前残留的接口，不能证明本轮已结束。同一轮次每类最终检查错误只报告一次；即使输入或边界随后变化，也不会重复同类诊断。每次输入错误、失配、API 违规和超时仍分别记录。已报告的错误保持到本轮清理；后续数据恢复匹配不能撤销它。

等待接口不会自动管理 phase objection；调用者应在等待期间保持运行 phase。

## 统计快照

`get_statistics` 返回独立对象，修改快照不会改变 scoreboard；快照也不会随之后的输入变化。统计只供查询，不自动输出汇总。内部累计计数均受保护；旧代码直接读取 `sb.matched_count`、`sb.mismatched_count` 或 `sb.dropped_count`，需迁移为读取快照中的同名字段。修改快照不会改变完成判断。

```systemverilog
general_scoreboard_statistics stats;
sb.get_statistics(stats);
```

| 字段 | 单位与含义 |
| --- | --- |
| `round_id` | 轮次编号，每次清理递增。 |
| `golden_packets`、`monitor_packets` | 合法输入 GP 包数，包含 IGNORE 与完全禁用的包。 |
| `golden_valid_bytes`、`monitor_valid_bytes` | 参与比较的有效字节数，排除禁用字节，IGNORE 为零。 |
| `golden_units`、`monitor_units` | 转换所得比较单元数；monitor 包含随后被过滤的单元。 |
| `compared_units` | 实际比较次数，包含重复读和失配，等于成功数加失配数。 |
| `covered_units` | 第一次成功比较的期望单元数，同一期望复读不重复增加。 |
| `retained_golden` | 实际保存的期望单元数，包含已覆盖但仍可复用的读模型。 |
| `matched_count`、`mismatched_count` | 成功与立即失配的比较单元数；普通 SET 无相等候选时保留为残留；复用读仍执行失配比较。 |
| `dropped_count` | 按过滤策略丢弃的比较单元数。 |
| `pending_golden`、`pending_monitor` | 尚未覆盖的保留期望数与待比较的 monitor 单元数。 |
| `unexpected_monitor` | 按当前过滤策略必需检查的 monitor 残留单元数。 |
| `expected_units`、`expected_set` | 预期比较单元数及有效标记；未显式设置时，数量在 golden 关闭后才有效。 |
| `expected_explicit` | 本轮数量是否来自成功的 set/add 调用，决定非空兜底是否停用。 |
| `input_errors`、`protocol_errors` | 输入校验错误与轮次 API 或容量错误次数。 |
| `timeout_count`、`check_errors` | 等待超时次数与本轮已报告的不同最终检查错误类别数。 |
| `golden_closed`、`monitor_closed` | 两条输入流的结束标记。 |
| `failed`、`complete` | 当前轮次的失败与完成状态。 |

## 清理与复位

`clear` 同步清空待匹配数据、历史身份、全部统计、预期数量、结束标记、保留的读模型、首次覆盖位和本轮错误状态，并允许重新配置。轮次编号递增，旧等待者返回 `RESET`，不会继续等待下一轮或污染下一轮的统计。`reset_phase` 自动调用同一接口。

清理不清除 UVM 全局已记录的错误。生产者应在清理期间停止提交；GP 不携带轮次号，清理后到达的数据会被视为新一轮输入。

## 包打印

`print_payload` 使用 GP 的标准行打印器，以一条 `UVM_INFO` 输出内容，支持报告 ID 与 verbosity。比较失败的两份 GP 也通过此接口打印。没有表格、文件报告、成功汇总或逐项历史记录；输入、比较、缺失、多余数据和容量错误保留 UVM 的错误级别。

```systemverilog
sb.print_payload(payload, "GP_DEBUG", UVM_HIGH);
```
