# Flow

## 定位

flow 负责把多个 operation 组织成可复用流程。flow 可以有输入字段和默认约束，不单独拆 request/response 类；调用者直接约束 flow sequence 自身字段。

flow 不直接做 scoreboard 比较。读写数据流由 `xfer_read_seq`、`xfer_write_seq` 执行，test 或上层 sequence 负责把读写期望交给 `agent.scb`。

## Initial

`initial_seq` 完成卡初始化并把 `ctx.has_initialized` 置位。

| 卡类型 | 命令过程 |
| --- | --- |
| eMMC | 400 kHz 分频、power up、clock check、CMD0、CMD1、CMD2、CMD3、CMD7、切到 `boot_cfg.frequence_legacy` |
| SD | 初始分频、CMD0、CMD8、ACMD41、可选 CMD11、CMD2、CMD3、CMD7、25 MHz、ACMD6 |
| SDIO | CMD5 查询、CMD5 带 S18R、可选 CMD11、CMD3、CMD7、CMD52 enable |

关键点：

- 初始化前的低频分频不做 clock frequency check。
- SD/SDIO 电压为 `V1_8` 时才走 CMD11。
- eMMC CMD1 的 OCR 使用 `cmd_request.ocr` 约束，默认 `32'h00ff8080`。
- `pre_switch_yield`、`post_switch_yield` 用于切状态前后留出回调插入点。

## Switch Bus

`switch_bus_seq` 输入：

| 字段 | 默认值 |
| --- | --- |
| `bus_speed_mode` | `settings.boot_cfg.default_bus_speed_mode` |
| `data_width` | `settings.boot_cfg.default_data_width` |

eMMC 过程：

1. 先把 clock 设到 6 MHz。
2. DDR 或 HS400 先切到 `HIGH_SPEED_SDR` 过渡。
3. CMD6 切 bus width。
4. CMD6 切 HS timing。
5. 按当前 `bus_speed_mode` 重新分频。

SD 过程：

1. ACMD6 切 bus width。
2. CMD6 switch function 切 speed mode。
3. 重新分频。

SDIO 过程：

1. CMD52 写 bus interface control。
2. CMD52 写 bus speed select。
3. 重新分频。

切换命令的 `post_start` 会更新 `ctx.data_width_cur` 或 `ctx.bus_speed_mode_cur`。

## Send EXT CSD

`send_ext_csd_seq` 只用于 eMMC。

| 字段 | 默认值 |
| --- | --- |
| `bus_speed_mode` | `settings.boot_cfg.default_bus_speed_mode` |
| `data_width` | `settings.boot_cfg.default_data_width` |

过程：

1. CMD13 查询 card status。
2. `switch_bus_seq` 切到目标速度。
3. CMD8 读 1 个 512-byte EXT_CSD block。

## Voltage Switch

`voltage_switch_seq` 只用于 SD/SDIO。

过程：

1. CMD11。
2. 等待 `settings.boot_cfg.voltage_switch_time_us`。

等待使用 `#1us` 循环，依赖 testbench timeunit/timeprecision 正确配置。

## Tune

`tune_seq` 输入：

| 字段 | 作用 |
| --- | --- |
| `phase` | 写入 tuning command request 的采样相位 |

过程：

1. 发送 tuning block command。
2. 约束 `cmd_request.phase == phase`。
3. 固定 `cmd_request.block_count == 1`。

## Command Wrapper

`commands.sv.j2` 和 `acmds.sv.j2` 是 command request 到 operation sequence 的轻封装。

关键点：

- 普通命令统一继承 `command_operation_seq#(<command>_request)`。
- ACMD 先发 APP_CMD，再发实际 ACMD。
- 会改变上下文的命令在 `post_start` 更新 `ctx`，例如 bus width、speed mode。
- command wrapper 不放流程判断，流程判断放具体 flow 或 operation。
