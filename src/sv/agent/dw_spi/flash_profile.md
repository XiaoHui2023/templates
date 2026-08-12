# Flash Profile

`dw_spi` 是控制器 agent，不负责判断实际挂载的是哪一种 flash。代码尽量把 SPI flash interaction 表达成通用 opcode/address/dummy/data transaction；具体 NOR、NAND、3-byte/4-byte address、XIP 或厂商扩展能力由指令包、flow、flash model 和用户环境负责。

当前 `flash_read`、`flash_write`、`rw_test` 是默认便捷 flow，按常见 SPI NOR 显式读写方式生成 transaction。默认 address phase 是 3 bytes，可通过配置传入 4 bytes。P25Q21L 命令表维护在用户根 skill `spi-flash-reference/references/commands/p25q21l.md`。

## Default Convenience Flow

| Field | Default |
| --- | --- |
| Flash family assumption for built-in read/write shortcuts | NOR-like explicit read/program |
| Address width | 3 bytes by default; 4 bytes may be passed by configuration |
| XIP | Not enabled by default |
| Read window | opcode + address + opcode-specific dummy cycles + data |
| Write window | opcode + address + data |
| WREN | Separate CS window |

SPI NAND 不直接复用这个 NOR-like byte memory flow。NAND 通常需要 page read-to-cache、cache read、program load、program execute、block erase、ECC/bad-block/status feature 等指令包和单独 flow。

## Command Mapping

| Operation | 1x standard | 1x enhanced | 2x | 4x |
| --- | --- | --- | --- | --- |
| Read | `0x03` | `0x0B` | `0xBB` | `0xEB` |
| Program | `0x02` | `0x02` | `0xA2` | `0x32` |

Other common P25Q21L commands recorded in the root skill include `RDID 0x9F`, `RDSR 0x05`, `RDSR2 0x35`, `WRSR 0x01`, `SE 0x20`, `BE32 0x52`, `BE64 0xD8`, `CE 0x60/0xC7`, `RSTEN 0x66`, and `RST 0x99`.

Program phase width is opcode-specific. `PP 0x02`, `DPP 0xA2`, and QPP `0x32` keep opcode/address single-lane; QPP changes only the payload phase to quad-lane. Read address width is also opcode-specific: `READ1X 0x03`, `FASTREAD1X 0x0B`, `DREAD 0x3B`, and `QREAD 0x6B` are single-lane address; `READ2X 0xBB` is dual-lane address; `READ4X 0xEB` is quad-lane address.

`STANDARD` / `ENHANCED` is the controller driving path, not always a flash opcode property. Compatible 1x commands such as `WREN 0x06`, `WRSR 0x01`, and `PP 0x02` may be executed through either standard or enhanced 1x controller setup. Opcodes that require dual/quad phases still force enhanced mode.

Executable command shapes are documented in [model/flash_command.md](model/flash_command.md). New flash opcodes should first get command packets, then be composed in flow sequences.

## Implemented Flow

Write:

```text
1x/2x:
  CS low -> 0x06 -> CS high
  CS low -> program opcode -> address -> data -> CS high

4x QPP:
  CS low -> 0x06 -> CS high
  CS low -> 0x01 -> 0x00 -> 0x02 -> CS high
  CS low -> 0x06 -> CS high
  CS low -> 0x32(1S) -> address(1S) -> data(4S) -> CS high
```

Read:

```text
CS low -> read opcode -> address -> opcode-specific dummy cycles -> data -> CS high
```

Non-DMA PIO does not split one flash program operation because the data is larger than the FIFO. It pre-fills up to the FIFO depth before selecting CS, then keeps the same CS window active while it waits for `SR.TFNF` and writes the remaining `DR` items. `CTRLR1.NDF` is derived from payload data frames, not instruction/address control entries or FIFO refill chunks. If the payload frame count exceeds `settings.ctrlr1_ndf_max`, the transfer is illegal for this IP configuration and the builder reports a fatal error.

Internal DMA uses the controller DMA registers and CPU callback staging path instead of PIO DR stream refilling.

## Current Verification Boundary

Implemented:

- WREN as a separate command-only transaction.
- QPP setup for 4x program: `WREN 0x06` sets WEL, `WRSR 0x01 + 16-bit status value 0x0200` sets `status[9] / SREG_QE`, then another `WREN 0x06` because WRSR clears WEL before `QPP 0x32`.
- QPP `0x32` is `1S-1S-4S`: `instruction_lanes=1`, `address_lanes=1`, and payload uses four lines. Therefore `SPI_CTRLR0.TRANS_TYPE=0` while `CTRLR0.SPI_FRF=2`; the 8-bit instruction takes 8 SCLK cycles and the default 24-bit address takes 24 SCLK cycles.
- Read/program opcode selection for 1x/2x/4x in the default NOR-like shortcuts.
- 3-byte or 4-byte address width by configuration, default 3.
- Read dummy clocks are command-owned SCLK cycles: `03h=0`, `0Bh=8`, `BBh=4`, and `EBh=6`; program/write windows do not use dummy clocks.
- `READ4X 0xEB` requests three additional receive bytes and discards those leading bytes before returning data to scoreboard (`rx_skip_bytes=3`).
- NDF derived only from payload data frames. Instruction/address/dummy remain in the same continuous CS window but are excluded from NDF.
- Scoreboard comparison using actual readback data from DR or DMA buffer.

Not yet implemented as full NOR behavior:

- Erase command before program.
- RDSR WIP polling and WEL checking after WREN/WRSR/program/erase.
- Skipping WRSR when QE is already set.
- Skipping repeated WRSR when QE state is already known to be set; command packets currently request the QE flow explicitly through `requires_qe`.
- 256-byte page boundary split/wrap/truncate behavior.
- Program bit rule where NOR only changes `1 -> 0` without erase.
- Unsupported command behavior per concrete model.

For simple controller smoke tests, the current default flow is usable. For flash-model-accurate P25Q21L tests, add erase/status/QE/page behavior before treating failures as protocol-complete.
