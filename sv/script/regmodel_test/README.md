# register_test

在已接好的寄存器模型与总线访问路径上，按配置选择并依次启动若干 UVM 自带的寄存器测试 sequence。

# Usage

- 在环境中为本 sequence 配置根寄存器模型（`uvm_reg_block`），并将默认 map 与总线侧 sequencer、adapter 按项目惯例关联；与本 sequence 绑定的 `p_sequencer` 须与该 map 一致。
- 布尔开关分别启用硬件复位、寄存器访问、存储器 HDL 路径与位翻转等内建序列。
- 若须让个别寄存器不参与内建测试：在 `start` 之前向序列成员 `no_test_regs` 填入对应 `uvm_reg` 句柄；`body` 会在启动内建 sequence 前为其中每个寄存器设置资源 `NO_REG_TESTS`。
