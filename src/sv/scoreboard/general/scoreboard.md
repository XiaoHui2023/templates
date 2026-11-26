# Scoreboard

主组件名称为 `<class_prefix>scoreboard`，辅助类型为 `<class_prefix>scoreboard_<角色>`。示例前缀为 `general_`，按原文拼接。

| 角色 | 示例类型名 |
| --- | --- |
| 主组件 | `general_scoreboard` |
| 配置 | `general_scoreboard_config` |
| 统计快照 | `general_scoreboard_statistics` |
| 观察回调 | `general_scoreboard_callback` |
| GP 转换与比较 | `general_scoreboard_adapter` |
| 内部记录与存储 | `general_scoreboard_entry`、`general_scoreboard_pending` |

## 输入与配置

两路输入均为 `uvm_tlm_generic_payload`，不接受自定义或派生载荷，不比较扩展、自定义字段或 DMI。golden 提供准确期望；monitor 可包含无关地址的数据。

```systemverilog
golden_producer.o_ap.connect(sb.i_golden_ap);
monitor.o_ap.connect(sb.i_monitor_ap);
```

在目标 scoreboard 的 `build_phase` 前设置配置。组件先使用生成默认值，再复制 `uvm_config_db` 中名为 `config` 的配置对象，最后应用已设置的 `uvm_config_db #(bit)` 单项并校验。运行期间重设数据库或修改原配置对象不会改变已生效的设置。

```systemverilog
general_scoreboard_config options;
options = new;
options.mode = general_scoreboard_config::ADDRESS;
options.reuse_read_expectations = 1;
options.expected_units = 4;
uvm_config_db #(general_scoreboard_config)::set(this, "sb", "config", options);
```

`checks_enabled` 默认开启。通过 `uvm_config_db #(bit)` 可以直接设置 `checks_enabled`、`require_golden`、`require_match`、`compare_address`、`compare_command`、`compare_data` 和 `compare_response`。显式设置 `expected_units` 时，两项非空策略仍由数量检查替代。

```systemverilog
// Full bypass for this instance in a special test.
uvm_config_db #(bit)::set(this, "env.sb", "checks_enabled", 0);

// Field-only override for a different instance that still checks transactions.
uvm_config_db #(bit)::set(this, "env.addr_sb", "compare_data", 0);
```

整体关闭时，组件保留端口和阶段调度，只统计采样期间跳过的包数，跳过载荷校验、比较与最终数据检查。配置校验仍执行，`on_check` 仍在 check phase 通知，统计中 `checks_enabled`、`checked` 和 `complete` 均为假。复位清零跳过计数并保留构建期设置。

## 自动生命周期

| UVM phase | 组件行为 |
| --- | --- |
| `build_phase` | 复制配置对象、读取单项开关并验证。 |
| `connect_phase` | 连接两路输入与类内 imp。 |
| `reset_phase` | 清除待匹配数据、历史地址、统计、错误和本轮阶段；保留构建期配置并递增轮次号。 |
| `extract_phase` | 在运行 phase 结束后冻结输入，排空延迟比较。 |
| `check_phase` | 检查开启时检查数量、首次覆盖、相关残留和错误。随后通知观察者。 |

采样应在运行 phase 中完成，生产者和 monitor 在实际工作结束前保持相应 objection。`main_phase` 结束不代表全部运行 phase 结束，`shutdown_phase` 仍可提交数据。`extract_phase` 是零时间函数阶段，不会等待 DUT 继续输出。

数量达到预期、队列暂空或静默一段时间，都不会提前标记成功。检查开启时，`is_complete` 在自动检查完成且没有错误后为真，冻结后再输入会报错并使先前的成功状态失效。组件不创建自己的 objection 或全局 watchdog；测试挂起超时使用 UVM root 的标准超时机制。

复位由标准 phase 调度触发，不需要调用 scoreboard 的清理方法。生产者应在复位期间停止提交；普通 GP 不带轮次号，组件不能辨认复位后的迟到旧数据。复位清除本轮状态，不清除 UVM 已累计的全局错误。

## 匹配与过滤

`ADDRESS` 允许不同地址乱序，同一身份按 FIFO 比较。`match_address`、`match_command` 决定候选身份，`compare_*` 决定选中后的比较字段；相关地址上的错误值会报错。默认地址参与身份，命令参与比较。

`SET` 在同一身份内逐个寻找相等候选，保留重复次数；无相等候选的数据暂存，最终检查缺失与多余数据。`ORDERED` 按全局顺序比较，忽略 `match_*`，仍执行 `compare_*`，因此输入应已过滤无关数据。

`DROP` 只接收已由 golden 登记的身份，要求对应 golden 先到；登记保留到复位，同址多余数据仍属相关残留。`BUFFER` 支持 monitor 先到，最终仅忽略从未由 golden 登记的残留。`STRICT` 对全部 monitor 残留报错。

每方向实际保留单元数、历史身份数及单包长度分别受 `max_pending`、`max_keys`、`max_payload_bytes` 限制。超限报 fatal，不自动淘汰数据。

## 地址写入终态

只关心各地址最终数据时，选择 `STATE`。组件在 golden 和 monitor 两侧分别保留每个有效字节地址的最后一次合法写入，在 `extract_phase` 冻结后比较。重复相同写入不会形成额外义务；中间错误值被后续正确写入覆盖可以通过，最后一次写入错误、缺少地址或 STRICT 下出现多余地址仍会失败。

```yaml
mode: state
atomize: true
match_address: true
reuse_read_expectations: false
monitor_policy: buffer
```

例如 golden 要求地址 0x1000 为 0x12：monitor 写 0x12 多次可通过，先写 0x34 再写 0x12 可通过，先写 0x12 再写 0x34 则失败。golden 自身多次更新同址也以最后值为准。不同分包、交叠写与循环 streaming 地址按有效字节依次更新，禁用字节不覆盖先前值。

STATE 要求 `atomize` 和 `match_address` 为真，不支持读期望复用及 READ 输入；IGNORE 不产生单元。每个包仍执行完整结构校验，非法输入造成的错误不会被后来正确写入清除。`compare_*` 字段选择照常生效；默认比较数据。STATE 不检查写入过程、次数、顺序或中间错误值，逐笔验证继续使用 ADDRESS、ORDERED 或 SET。

过滤策略保持一致。推荐 BUFFER 收集两侧终态并忽略从未声明的地址；DROP 会丢弃 golden 登记前的 monitor 写入，STRICT 对无关地址残留也报错。STATE 的 `max_pending` 约束保留的独立地址数，同址重复不会持续占用新位置；`max_keys` 仍限制 golden 历史身份数。

## GP 与比较单元

数组内容与有效长度分别设置，`set_data_length`、`set_byte_enable_length` 不得超过数组容量。字节使能仅接受 00/ff，短掩码按周期重复；IGNORE 和完全禁用的包不产生比较单元。

`atomize` 为真时，每个有效字节为一个比较单元，可比较不同分包方式。地址为起始地址加字节序号对有效 streaming width 的余数；width 为 0 或不小于有效长度时按连续地址处理。保留 64 位地址并检查回绕，不做隐含端序转换。

整包模式每个参与比较的 GP 为一个单元，同时比较有效长度、有效 streaming width 和选择的字段。有效字节位置必须一致，禁用位置的数据值被忽略。输入内容由组件独立保存，生产者复用句柄不会改动已有期望。

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
```

## 读期望复用

在 ADDRESS、ORDERED、SET 模式中，开启 `reuse_read_expectations` 后，读模型保留到复位，每个相关读样本都比较；写期望仍一对一消费。已覆盖的读仍可能产生后续失配，不会去重丢弃。相同 golden 多次提交形成多个独立义务。

读样本在 `extract_phase` 确定完整期望集合后逐条处理，优先覆盖未覆盖的相等模型，再复用已覆盖的相等模型；没有相等模型时仍比较并报失配。此前全部读样本占用 `max_pending`，大量采样应配置足够容量。不会用提前消费第一条模型的方式掩盖后续同址期望缺失。

ORDERED 保持首次覆盖及写操作的顺序，已覆盖读可穿插复读，后续未覆盖读不能跨越前置写。复用开启时读写命令始终区分，不受普通模式忽略命令设置的影响。

## 数量与非空策略

`expected_units` 是构建期预期比较单元数；-1 使用最终 `required_units`，非负值同时检查期望义务数和首次成功覆盖数。STATE 的义务是 golden 中独立有效字节地址，其余模式每个 golden 转换单元形成独立义务。显式数量停用 `require_golden`、`require_match`，包括显式 0；推导数量不会停用它们。

未显式声明时，`require_golden` 检查至少收到一包合法 golden，包含 IGNORE 和完全禁用包；`require_match` 检查至少有一个比较单元成功匹配，两项默认开启。显式 0 允许空轮次，仍需运行 phase 正常结束、无错误且无相关残留。

事务模式比较次数包含重复读及失配，STATE 每个最终地址对比较一次；首次覆盖数仅对每条期望的第一次成功增加；重复读不能补偿未覆盖地址。包数、有效字节数和比较单元数分别统计，预期数量只使用比较单元。

## 观察回调

可派生 `general_scoreboard_callback` 并通过标准 `uvm_callbacks` 注册，不需要派生 scoreboard。三个钩子 `on_reset`、`on_compare`、`on_check` 默认无操作；在发生相应事件前注册，支持标准 callback enable/disable。

```systemverilog
uvm_callbacks #(general_scoreboard, general_scoreboard_callback)::add(sb, observer);
```

`on_reset` 接收组件路径和清理后的统计。`on_compare` 接收路径、golden/monitor 比较单元、成功标记、首次覆盖标记及比较后的统计。`on_check` 接收路径和阶段结束时的统计，可查看 `checked` 确认是否执行了检查。

每个观察者分别收到独立 GP 标准字段副本和统计快照，修改通知参数不会改变模型或后续观察者。回调是同步函数，不消耗仿真时间；回调执行期间再次向此 scoreboard 输入会报错，避免递归修改正在比较的数据。回调不提供配置或内部状态句柄。

## 统计查询与打印

`get_statistics` 返回独立快照，不打印也不改变状态。`is_complete` 是只读查询，不触发检查。

```systemverilog
general_scoreboard_statistics stats;
sb.get_statistics(stats);
```

| 字段 | 含义 |
| --- | --- |
| `round_id` | 每次构造或标准复位清理时递增。 |
| `checks_enabled` | 构建期解析后生效的总开关。 |
| `skipped_packets` | 检查关闭时在采样期间跳过的双端输入包数，复位清零。 |
| `golden_packets`、`monitor_packets` | 合法输入 GP 包数，包含 IGNORE 与完全禁用包。 |
| `golden_valid_bytes`、`monitor_valid_bytes` | 有效字节数，排除禁用位置，IGNORE 为零。 |
| `golden_units`、`monitor_units` | 转换所得比较单元数，monitor 包含随后被过滤的单元。 |
| `required_units` | 当前策略的期望义务数；STATE 为独立 golden 地址数，其余为 golden_units。 |
| `compared_units` | 比较次数，等于 `matched_count + mismatched_count`。 |
| `covered_units` | 首次成功覆盖的期望单元数。 |
| `retained_golden` | 保存的全部模型数，包含已覆盖的可复用读；STATE 为尚保留的终态地址。 |
| `matched_count`、`mismatched_count`、`dropped_count` | 成功比较、失配和过滤单元数。 |
| `pending_golden`、`pending_monitor`、`unexpected_monitor` | 未覆盖期望、待处理实际单元和必须检查的实际残留。 |
| `expected_units`、`expected_set`、`expected_explicit` | 有效预期数、数量是否已知、是否由配置显式声明。 |
| `input_errors`、`protocol_errors`、`check_errors` | 输入校验、非法时机或重入、最终检查错误项数。 |
| `sealed`、`checked` | 输入已冻结、自动检查已执行。 |
| `failed`、`complete` | 当前失败与最终成功状态。 |

`print_payload` 通过 GP 标准行打印器，以一条 `UVM_INFO` 输出包，支持 ID 与 verbosity。失配包也使用同一入口；没有统计表格、文件报告或成功汇总。

```systemverilog
sb.print_payload(payload, "GP_DEBUG", UVM_HIGH);
```

## 迁移

Models 省略 mode 时默认 ADDRESS，原有模式逐笔语义保持；随库 example.yaml 显式选择 STATE/BUFFER。需要忽略同址写入细节时显式选择 STATE；STATE 的 expected_units 使用独立地址数，不能沿用写入次数。

旧的 `configure`、`clear`、`set_expected_units`、`add_expected_units`、`end_golden`、`end_monitor`、`end_round`、`check_pending`、`check_round`、`pending_counts` 和 `wait_complete` 不再作为外部 API。配置使用构建期 `config_db`，采样结束、清理与检查交给 phase；运行时追加数量或手动开启多个轮次的用法需要调整。

统计中的 `golden_closed`、`monitor_closed` 改为统一的 `sealed` 与 `checked`，不再提供自建等待超时统计。独立时间服务包随旧等待接口移除。已有 `i_golden_ap`、`i_monitor_ap`、只读统计查询和标准打印用法保持。
