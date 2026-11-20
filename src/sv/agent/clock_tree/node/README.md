# 新增节点

以固定分频节点 `custom_div` 为例。它接一个输入，不写寄存器，按 ratio 计算输出频率。

## 定义输入属性

创建 `node/python/plugins/custom_div.py`：

```python
from pydantic import Field
from ..config import NodePluginConfig


class CustomDivConfig(NodePluginConfig):
    ratio: int = Field(default=2, ge=1)
```

在 `node/python/registry.py` 导入该类，并向 `PLUGIN_CONFIGS` 添加 `"custom_div": CustomDivConfig`。

ratio 与 kind、source 平级。公共模型负责连接和路径，插件负责自己的属性；不要把 ratio 加到公共 Models。

## 定义 SV 行为

创建 `node/plugin/custom_div.sv.j2`：

```systemverilog
class {{ settings.class_prefix }}custom_div extends {{ settings.class_prefix }}node_base;
    `uvm_object_utils({{ settings.class_prefix }}custom_div)

    int ratio = 2;

    constraint cst_resolve_freq_from_src {
        source != null -> _resolved_freq == source._resolved_freq / ratio;
    }

    function new(string name = "");
        super.new(name);
    endfunction

    virtual function real clock_rate_hz();
        return source == null ? 0.0 : source.clock_rate_hz() / real'(ratio);
    endfunction
endclass
```

同名约束替换默认的直通频率约束；活动状态仍继承前级。这个例子只处理固定分频，不提供寄存器配置或 flip。实际可编程分频器还要处理编码、复位、load 和恢复。

将 `node/plugin/custom_div.sv` 加入 `config.f.j2` 的公共 files 宏，放在基类之后。完整编译也使用这份节点清单，不需要再建自动发现机制。

## 使用

```yaml
nodes:
  osc:
    kind: source
    frequence: 24000000
  custom0:
    kind: custom_div
    source: osc
    ratio: 2
  clk_out:
    kind: clk
    source: custom0
    path: dut.clk_out
    frequence: 12000000
```

生成后检查 custom0.ratio 为 2、clk_out 的 source 指向 custom0。build 后输出应为 12 MHz；实际测量需要 DUT 确实提供该信号。

## 增加能力

- **寄存器配置**：Python 校验字段并返回绑定要求；SV 声明控制寄存器、配置动作及重复配置判断。
- **多输入、多输出**：Python 分配端口，SV 通过输入键和 output_peers 处理连接；公共 tree 不增加节点分支。
- **测量**：声明可测量输出、占空比策略、平均窗口和最大边沿间隔。
- **功能检查**：实现自身激励与预期；公共入口负责保存、恢复和释放。

具体接口见 [钩子参考](hooks.md)。普通配置、低功耗、功能检查和临时供钟都通过相同节点对象工作，不复制一份专用节点。
