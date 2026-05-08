# ral_test

在已接好的寄存器抽象层（RAL）与总线访问路径上，按布尔开关依次启动若干 UVM 内建寄存器测试 sequence。

# Usage

- 在环境中为本 sequence 配置根寄存器模型（`uvm_reg_block`），并将默认 map 与总线侧 sequencer、adapter 按项目惯例关联；与本 sequence 绑定的 `p_sequencer` 须与该 map 一致。
- 通过各布尔开关分别启用硬件复位、寄存器访问、存储器 HDL 路径与位翻转等内建序列。
- 若要让个别寄存器跳过内建测试：在 `start` 之前向成员 `no_test_regs` 填入对应 `uvm_reg` 句柄；序列在启动各内建 sequence 之前为其中每个寄存器设置资源 `NO_REG_TESTS`。
