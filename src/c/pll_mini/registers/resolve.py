from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from model.consolver import _SmtBuilder, solve_tree_with_consolver
from model.freq_graph import output_ports
from model.nodes import Tree
from model.solve_model import SolveModel
from model.verify import raise_on_verify_issues, verify_solve_model


@dataclass(frozen=True)
class ResolvedNode:
    """插件参数与已解端口频率，供寄存器规划读取。"""

    name: str
    kind: str
    resolved_freq: int
    port_freqs: dict[str, int]
    values: dict[str, object] = field(default_factory=dict)

    def __getattr__(self, name: str) -> object:
        """读取插件提供的寄存器规划状态。"""
        try:
            return self.values[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


@dataclass(frozen=True)
class TreeResolve:
    """图求解及插件参数解析结果。"""

    by_name: dict[str, ResolvedNode]
    target_names: tuple[str, ...]
    solve_model: SolveModel


def resolve_tree(
    tree: Tree,
    *,
    period_tolerance: float,
    solve_timeout_ms: int | None = None,
    debug_consolver_smt_path: Path | None = None,
    reg_index=None,
    plugin_settings=None,
) -> TreeResolve:
    """求解频率图、调用插件参数推算并回放验证。

    Raises:
        ValueError: 没有目标节点或公式回放失败。
        RuntimeError: 图无解、工具失败或插件参数无法配置。
    """
    targets = [node.name for node in tree.nodes_ordered if node.is_target]
    if not targets:
        raise ValueError("nodes 须至少含一个声明频率目标的插件节点")
    model = solve_tree_with_consolver(
        tree,
        period_tolerance=period_tolerance,
        timeout_ms=solve_timeout_ms,
        debug_smt_path=debug_consolver_smt_path,
        reg_index=reg_index,
    )
    if plugin_settings is None:
        from node.registry import default_plugin_settings

        plugin_settings = default_plugin_settings(period_tolerance=period_tolerance)

    def failure_artifact(stage, error, **details):
        builder = _SmtBuilder(
            tree, period_tolerance=period_tolerance, reg_index=reg_index
        )
        path = builder.failure_path(debug_consolver_smt_path)
        builder.write_debug(
            path,
            {
                "status": stage,
                "error": str(error),
                "active": model.active,
                "port_freq": [
                    {"node": port.node, "group": port.group, "hz": hz}
                    for port, hz in model.port_freq.items()
                ],
                "node_values": model.node_values,
                **details,
            },
        )
        return f"SMT: {path}\n映射: {path.with_suffix('.json')}"

    for node in tree.nodes_ordered:
        try:
            node.fit(tree, model, plugin_settings)
        except (ValueError, RuntimeError) as exc:
            artifact = failure_artifact("fit_error", exc, node=node.name)
            raise RuntimeError(
                f"[fit] nodes[{node.name!r}] kind={node.kind}: {exc}\n{artifact}"
            ) from exc
    issues = verify_solve_model(tree, model, period_tolerance=period_tolerance)
    if issues:
        artifact = failure_artifact(
            "verify_error",
            "formula replay failed",
            issues=[asdict(issue) for issue in issues],
        )
        try:
            raise_on_verify_issues(tree, issues)
        except ValueError as exc:
            raise ValueError(f"[verify] {exc}\n{artifact}") from exc
    resolved = {}
    for name, node in tree.nodes.items():
        ports = {
            port.group: model.port_hz(port) or node.fixed_hz(port.group) or 0
            for port in output_ports(tree, name)
        }
        primary = ports.get(node.primary_output_group, next(iter(ports.values()), 0))
        resolved[name] = ResolvedNode(
            name=name,
            kind=node.kind,
            resolved_freq=primary,
            port_freqs=ports,
            values=node.resolved_values(model),
        )
    return TreeResolve(resolved, tuple(targets), model)
