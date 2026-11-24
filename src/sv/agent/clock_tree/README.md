# clock_tree

根据时钟连接和寄存器配置，生成可配置、可检查的 SystemVerilog 时钟树模型。

- **配置**：指定时钟频率和开关，求解分频、选路及门控，再写入寄存器。
- **测量**：检查信号是否有时钟、频率是否正确、占空比是否合格。
- **功能测试**：驱动单个器件输入，遍历控制寄存器并检查输出。
- **连线测试**：观察已有激励或探测空闲前级，检查后级输入是否跟随。

## 最小配置

24 MHz 晶振经过一个可编程 gate，输出到 CPU 时钟。

```yaml
settings:
  class_regmodel: chip_regmodel

nodes:
  osc:
    kind: source
    frequence: 24000000

  gate_cpu:
    kind: gate
    source: osc
    reg: clk_ctrl.cpu_gate

  clk_cpu:
    kind: clk
    source: gate_cpu
    path: dut.clk_cpu
    frequence: 24000000
```

`source` 描述设计连接，`reg` 指向寄存器模型字段，`path` 指向 RTL 信号。节点填写正频率且没有显式设置 enabled 时，clk 默认开启。

完整器件与多输入示例保存在 [example.yaml](example.yaml) 和 [example_nodes.yaml](example_nodes.yaml)。

## 使用

1. 按 [输入配置](configuration.md) 填写节点、路径和寄存器字段。
2. 用下面的命令生成文件。完整验证编译 `all.f`；只配置寄存器时启用 `direct_config`，编译 `config.f`。
3. 创建 tree 并绑定寄存器，按 [模型](model/README.md) 设置目标、执行配置。
4. 需要检查时例化接口，按 [接口](top/interface.md) 绑定信号，通过 [组件](component/README.md) 启动检查。

两个 filelist 均用 `-F` 引入，内部相对路径从 filelist 所在目录解析。`config.f` 不包含接口、组件和 sequence，但仍需要 UVM 及用户寄存器模型。

在 templates 仓库根目录执行，`JINJA_BUILD` 指向已安装依赖的 [jinja-build](https://github.com/XiaoHui2023/jinja-build) 源码目录：

```sh
JINJA_BUILD=/path/to/jinja-build
python "$JINJA_BUILD/src/__main__.py" \
  -t src/sv/agent/clock_tree \
  -i src/sv/agent/clock_tree/example.yaml \
  -o generated/clock_tree
```

将生成目录加入工程编译清单，二选一：

```text
-F generated/clock_tree/all.f
```

```text
-F generated/clock_tree/config.f
```

先编译 UVM 和用户寄存器模型，并让生成的类可见 `uvm_pkg`、UVM 宏及 `class_regmodel` 类型；具体导入方式沿用工程的编译单元组织。生成目录的 README 给出接口例化与 agent 搭建代码；启用 direct_config 后的 config.md 给出纯配置代码。

## 扩展

[结构](architecture.md) 说明公共代码与插件的关系。[新增节点](node/README.md) 从一个固定二分频器开始；[钩子参考](node/hooks.md) 按配置、测量和功能列出可重载接口。

检查的区别和选择见 [sequence](sequence/README.md)，寄存器编码与频率换算见 [计算公式](core/formulas.md)。

旧接口的变动见 [版本记录](VERSIONS.md)。
