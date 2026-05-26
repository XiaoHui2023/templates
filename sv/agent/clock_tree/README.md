# clock_tree

用于芯片验证的时钟树 agent。

- 支持多棵 **tree**；每棵平铺节点、**randomize** 典型频率，并对 **clk**、**pll** 做软约束。
- 各节点 **interface** 做频率与占空比测量。
- 可选 **setting_defs**；每棵 **tree** 自带 **settings**，在检查前由 **kit_sequencer** 便捷方法完成系统配置。
- 可选 **class_regmodel** 与节点寄存器 field 路径；**connection** 建树时绑定 **uvm_reg_field**。
- **sequence/behavior** 按行为分子目录；**kit_interface** 在 **agent.sqr** 上启动行为并读取 **rsp**。

# 相关文档

- [数据模型](model.md)
- [UVM 组件](component.md)
- [回调](callback.md)
