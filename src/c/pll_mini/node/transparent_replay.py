from __future__ import annotations


def verify_node(node, tree, model, period_tolerance):
    from model.freq_graph import (
        node_has_upstream_ref,
        output_ports,
        parent_port_for_child,
        port_label,
    )
    from model.verify import VerifyIssue, _hz_mhz, _path_for_node

    issues = []
    for name, node in [(node.name, node)]:
        if not node_has_upstream_ref(node):
            continue
        parent_port = parent_port_for_child(tree, name)
        f_parent = model.port_hz(parent_port)
        out_ports = output_ports(tree, name)
        if not out_ports:
            continue
        f_self = model.port_hz(out_ports[0])
        if f_parent <= 0 or f_self <= 0:
            continue
        if f_parent != f_self:
            issues.append(
                VerifyIssue(
                    headline=f"{node.kind} {name} 未透传前级频率",
                    formula="f_out = f_ref",
                    detail=(
                        f"前级 {port_label(parent_port, tree)} "
                        f"{_hz_mhz(f_parent)}，"
                        f"本节点 {_hz_mhz(f_self)}"
                    ),
                    path_nodes=_path_for_node(tree, name, model),
                )
            )

    return issues
