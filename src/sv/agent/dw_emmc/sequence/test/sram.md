# SRAM Overflow

## 结论

不保留 `sram_test`。

控制器 SRAM 接近满时不会继续无节制接收数据直到溢出。当前 IP 行为是通过停止 card clock 做背压，等 host 侧读取 `BUF_DATA_R` 释放空间后再继续传输。因此，用“先不读 buffer，等传输超过 SRAM 容量后检查第一块是否被最后一块覆盖”的方式验证 SRAM 溢出，和控制器实际保护机制不一致。

## 原始意图

原测试想验证以下假设：

- host 先写入 `sram_size + block_size` 的数据作为 card memory 期望内容。
- host 发起 read 后暂不读取 controller buffer。
- 如果读入数据超过 SRAM 容量，旧数据会被后续 block 覆盖。
- 通过比较第一块和溢出的最后一块，判断 SRAM 覆盖行为。

这个假设不成立。控制器不会让 SRAM 正常爆掉，而是在接近满时暂停时钟，阻止 card 继续送数。

## 取消原因

- 该场景不是普通 read/write 功能测试，也不是 scoreboard memory 一致性测试。
- 等待 `XFER_COMPLETE` 后再一次性读取超出 SRAM 容量的数据，可能永远等不到完成，因为完成条件依赖 host 先读取 buffer 释放空间。
- 按 block 等待 `BUF_RD_READY` 但故意不读走数据，也会停在第一段 ready 后，后续 ready 不再产生。
- 继续保留该 test 会把控制器的背压保护误判为测试失败或 SRAM 覆盖失败。

## 正确关注点

SRAM 相关行为应按 flow control 理解：

- `BUF_RD_READY` 表示 host 可以从 `BUF_DATA_R` 取数。
- host 读走 buffer 后，控制器才有空间继续接收后续数据。
- 接近满时停 card clock 是保护行为，不是 overflow bug。
- 普通 PIO read 应保持“ready 后立即取数”的节奏。

公开 Linux SDHCI/DWC MSHC 驱动把 `SDHCI_PRESENT_STATE.DATA_AVAILABLE`、`SDHCI_BUFFER`、`SDHCI_CLOCK_CONTROL.CARD_EN` 作为数据可取、buffer 访问和 card clock 控制的公开实现锚点；具体 SRAM 深度和停时钟阈值属于 IP 实现细节。
