# register_test

在已接好的寄存器模型与总线访问路径上，按配置选择并依次启动若干 UVM 自带的寄存器测试 sequence。

# Usage

- 在环境中为本 sequence 配置根寄存器模型（`uvm_reg_block`），并将默认 map 与总线侧 sequencer、adapter 按项目惯例关联；与本 sequence 绑定的 `p_sequencer` 须与该 map 一致。
- 布尔开关分别启用硬件复位、寄存器访问、存储器 HDL 路径与位翻转等内建序列。
- 若须对个别寄存器跳过自带测试，在环境中按项目对 UVM 寄存器测试的惯例处理。
