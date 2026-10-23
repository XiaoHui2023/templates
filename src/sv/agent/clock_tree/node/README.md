# 节点

## 配置

```yaml
gate_cpu:
  kind: gate
  source: pll_cpu
  reg: clk_ctrl.cpu_gate
  config:
    open: 1
```

节点通用字段由树处理，`config` 由 `kind` 对应的 Python 插件校验。多输出节点可用 `output_config` 覆盖单个输出组。

```yaml
pll_cpu:
  kind: pll_inno
  outputs: [core, bus]
  config:
    enabled: 1
  output_config:
    core:
      frequence: 1000000000
    bus:
      frequence: 500000000
```

## 契约

| 能力 | 基础 hook | 节点插件负责内容 |
| --- | --- | --- |
| 拓扑 | `set_source`、`collect_source_nodes`、`collect_input_keys_from_source` | 上游与端口键 |
| 配置 | `configuration_priority`、`apply_configuration`、`await_configuration` | 配置顺序、寄存器动作、完成条件 |
| 观测 | `is_observable`、`supports_duty_observation`、`is_stability_anchor` | 可测端点、占空比、稳定性 |
| 低功耗 | `apply_low_power_preference` | 节点低功耗偏好 |
| 功能 | `has_functional_contract`、`run_functional_contract` | 端口激励与输出检查 |
| 原生输入 | `preserves_native_input` | 禁止驱动的原生时钟输入 |

## 扩展

添加节点时同时添加以下文件，并在各自清单中显式登记：

```text
node/plugin/<kind>.sv.j2
node/python/plugins/<kind>.py
```

Python 插件声明可填写的 `config` 与 `settings.plugin.<作用域>` 字段；后者也在
`node/python/registry.py` 显式登记。SV 插件声明约束、寄存器编码和能力 hook。未知
`kind` 仍会保留配置并生成对应 SV 类型，缺少 SV 插件时由编译报错。
