# Flash Profile

`dw_spi` 默认按 SPI NOR 3-byte address profile 生成和验证 flash transaction。当前默认命令映射参考用户提供的 P25Q21L 命令表；完整命令表维护在用户根 skill `spi-flash-reference/references/commands/p25q21l.md`。

## Default Type

| Field | Default |
| --- | --- |
| Flash type | SPI NOR |
| Address width | 3 bytes |
| XIP | 不默认启用 |
| Read/write window | opcode + address + 1 dummy byte + data |
| WREN | 单独 CS window |

SPI NAND 不使用这套 flow。SPI NAND 需要 page/cache/ECC/bad-block 模型，不能直接复用 NOR 的 byte memory mirror。

## Command Mapping

| Operation | 1x standard | 1x enhanced | 2x | 4x |
| --- | --- | --- | --- | --- |
| Read | `0x03` | `0x0B` | `0xBB` | `0xEB` |
| Program | `0x02` | `0x02` | `0xA2` | `0x32` |

Other common P25Q21L commands recorded in the root skill include `RDID 0x9F`, `RDSR 0x05`, `RDSR2 0x35`, `WRSR 0x01`, `SE 0x20`, `BE32 0x52`, `BE64 0xD8`, `CE 0x60/0xC7`, `RSTEN 0x66`, and `RST 0x99`.

## Implemented Flow

Write:

```text
1x/2x:
  CS low -> 0x06 -> CS high
  CS low -> program opcode -> address -> dummy byte -> data -> CS high

4x QPP:
  CS low -> 0x06 -> CS high
  CS low -> 0x01 -> 0x00 -> 0x02 -> CS high
  CS low -> 0x06 -> CS high
  CS low -> 0x32 -> address -> dummy byte -> data -> CS high
```

Read:

```text
CS low -> read opcode -> address -> dummy byte -> data -> CS high
```

Non-DMA PIO does not split one flash program operation because the data is larger than the FIFO. It pre-fills up to the FIFO depth before selecting CS, then keeps the same CS window active while it waits for `SR.TFNF` and writes the remaining `DR` bytes. `CTRLR1.NDF` is derived from the full program stream, not from each FIFO refill. If the full stream exceeds `settings.ctrlr1_ndf_max`, the transfer is illegal for this IP configuration and the builder reports a fatal error.

Internal DMA uses the controller DMA registers and CPU callback staging path instead of PIO DR stream refilling.

## Current Verification Boundary

Implemented:

- WREN as a separate command-only transaction.
- QPP setup for 4x program: `WREN 0x06` sets WEL, `WRSR 0x01 + 16-bit status value 0x0200` sets `status[9] / SREG_QE`, then another `WREN 0x06` because WRSR clears WEL before `QPP 0x32`.
- Read/program opcode selection for 1x/2x/4x.
- 3-byte or 4-byte address width by configuration, default 3.
- One dummy byte by default for read/program data windows.
- NDF derived from the full continuous window: opcode + address + dummy + data.
- Scoreboard comparison using actual readback data from DR or DMA buffer.

Not yet implemented as full NOR behavior:

- Erase command before program.
- RDSR WIP polling and WEL checking after WREN/WRSR/program/erase.
- Skipping WRSR when QE is already set.
- QE/WRSR flow before quad read when the flash model requires it.
- 256-byte page boundary split/wrap/truncate behavior.
- Program bit rule where NOR only changes `1 -> 0` without erase.
- Unsupported command behavior per concrete model.

For simple controller smoke tests, the current flow is usable. For flash-model-accurate P25Q21L tests, add erase/status/QE/page behavior before treating failures as protocol-complete.
