from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Iterator, Mapping, Sequence

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.text import Text
from rich.theme import Theme

from model.freq_graph import parent_port_for_child
from model.nodes import ClkNode, DivNode, MuxNode, PllNode, Tree, parse_source_endpoint

_THEME = Theme(
    {
        "progress.title": "#61afef",
        "progress.stage": "#abb2bf",
        "progress.ok": "#98c379",
        "progress.clk": "#98c379",
        "progress.dim": "#5c6370",
        "tree.kind": "#56b6c2",
        "tree.target": "#e5c07b",
        "tree.clk": "#98c379",
    }
)

_SESSION_LOCK = threading.Lock()
_ACTIVE_SESSION: ProgressSession | None = None


def active_progress_session() -> ProgressSession | None:
    with _SESSION_LOCK:
        return _ACTIVE_SESSION


def bind_progress_session(session: ProgressSession) -> None:
    _set_active_session(session)


def unbind_progress_session(session: ProgressSession) -> None:
    if active_progress_session() is session:
        _set_active_session(None)


def _set_active_session(session: ProgressSession | None) -> None:
    global _ACTIVE_SESSION
    with _SESSION_LOCK:
        _ACTIVE_SESSION = session


def _hz_mhz(hz: int) -> str:
    if hz % 1_000_000 == 0:
        return f"{hz // 1_000_000} MHz"
    if hz % 1_000 == 0:
        return f"{hz / 1_000:.3f} kHz"
    return f"{hz} Hz"


def _human_stage_name(component: str, action: str, label: str) -> str:
    if component == "models" and action == "load":
        return "加载寄存器模型"
    if component == "ralfconv" and action == "flat":
        return "ralfconv 解析 RALF"
    if component == "models" and action == "compute":
        if label == "tree_resolve":
            return "频率图求解"
        if label == "config_plan":
            return "生成配置计划"
        if label == "header_regs":
            return "收集头文件寄存器"
    if component == "search" and action == "solve":
        return "时钟树约束求解"
    if component == "search" and action == "partition":
        return "分割连通域"
    if component == "search" and action == "component":
        return f"子树 {label}"
    if component == "search" and action == "merge":
        return "合并子树模型"
    if component == "resolve" and action == "fit":
        return "反推 PLL 系数"
    if component == "resolve" and action == "verify":
        return "公式回放验证"
    if component == "resolve" and action == "nodes":
        return "解析节点频率"
    if component == "diagnose" and action == "collect":
        return f"诊断收集 {label}"
    if component == "diagnose" and action == "format":
        return f"诊断排版 {label}"
    return f"{component} · {action} · {label}"


def _collect_parents_in_set(
    tree: Tree,
    names_set: set[str],
) -> dict[str, tuple[str, ...]]:
    parents: dict[str, list[str]] = {name: [] for name in names_set}
    for name in names_set:
        node = tree.nodes[name]
        if node.kind == "source":
            continue
        if isinstance(node, MuxNode):
            for arm in node.source.values():
                arm_name, _ = parse_source_endpoint(arm, ctx="parent")
                if arm_name in names_set:
                    parents[name].append(arm_name)
            continue
        try:
            parent = parent_port_for_child(tree, name)
        except ValueError:
            continue
        if parent.node in names_set:
            parents[name].append(parent.node)
    return {
        name: tuple(sorted(dict.fromkeys(items)))
        for name, items in parents.items()
    }


def _longest_path_layers(
    names_set: set[str],
    parents: Mapping[str, tuple[str, ...]],
) -> dict[str, int]:
    layers = {name: 0 for name in names_set}
    for _ in range(len(names_set)):
        changed = False
        for name in names_set:
            for parent in parents.get(name, ()):
                if parent not in names_set:
                    continue
                candidate = layers[parent] + 1
                if candidate > layers[name]:
                    layers[name] = candidate
                    changed = True
        if not changed:
            break
    return layers


def _node_tree_label(
    tree: Tree,
    name: str,
    target_hz: Mapping[str, int],
) -> Text:
    node = tree.nodes[name]
    kind = getattr(node, "kind", "?")
    if isinstance(node, DivNode):
        kind = node.div_kind
    label = Text()
    if name in target_hz:
        label.append("◆ ", style="bold progress.clk")
    label.append(name, style="bold")
    label.append(f" [{kind}]", style="tree.kind")
    if name in target_hz:
        label.append(f" → {_hz_mhz(target_hz[name])}", style="tree.target")
    elif isinstance(node, ClkNode) and node.freq is not None and node.freq > 0:
        label.append(f" → {_hz_mhz(node.freq)}", style="tree.target")
    elif isinstance(node, PllNode) and node.freq is not None and node.freq > 0:
        label.append(f" → {_hz_mhz(node.freq)}", style="tree.target")
    elif isinstance(node, DivNode) and node.ratio is not None:
        label.append(f" ratio={node.ratio}", style="tree.target")
    elif isinstance(node, MuxNode) and node.sel is not None:
        label.append(f" sel={node.sel}", style="tree.target")
    return label


def _node_plain_tag(
    tree: Tree,
    name: str,
    target_hz: Mapping[str, int],
) -> str:
    node = tree.nodes[name]
    kind = getattr(node, "kind", "?")
    if isinstance(node, DivNode):
        kind = node.div_kind
    parts = [name, f"[{kind}]"]
    if name in target_hz:
        parts.append(f"→{_hz_mhz(target_hz[name])}")
    elif isinstance(node, ClkNode) and node.freq is not None and node.freq > 0:
        parts.append(f"→{_hz_mhz(node.freq)}")
    elif isinstance(node, PllNode) and node.freq is not None and node.freq > 0:
        parts.append(f"→{_hz_mhz(node.freq)}")
    elif isinstance(node, DivNode) and node.ratio is not None:
        parts.append(f"ratio={node.ratio}")
    elif isinstance(node, MuxNode) and node.sel is not None:
        parts.append(f"sel={node.sel}")
    return " ".join(parts)


def _append_node_label(
    line: Text,
    tree: Tree,
    name: str,
    target_hz: Mapping[str, int],
) -> None:
    line.append_text(_node_tree_label(tree, name, target_hz))


def _append_edge_line(
    out: Text,
    *,
    indent: str,
    left: Text,
    arrow: str,
    right: Text | None = None,
) -> None:
    out.append(indent)
    out.append_text(left)
    out.append(arrow, style="progress.dim")
    if right is not None:
        out.append_text(right)
    out.append("\n")


def _render_fan_in_block(
    out: Text,
    tree: Tree,
    target_hz: Mapping[str, int],
    block: Sequence[tuple[str, str]],
    dst: str,
) -> None:
    width = max(len(_node_plain_tag(tree, edge_src, target_hz)) for edge_src, _ in block)
    right = Text()
    _append_node_label(right, tree, dst, target_hz)
    for edge_index, (edge_src, _) in enumerate(block):
        left = Text()
        _append_node_label(left, tree, edge_src, target_hz)
        pad = " " * max(0, width - len(_node_plain_tag(tree, edge_src, target_hz)))
        if edge_index < len(block) - 1:
            _append_edge_line(out, indent=f"  {pad}", left=left, arrow=" ─┐")
        else:
            _append_edge_line(out, indent=f"  {pad}", left=left, arrow=" ─┼→ ", right=right)


def _render_fan_out_block(
    out: Text,
    tree: Tree,
    target_hz: Mapping[str, int],
    block: Sequence[tuple[str, str]],
    src: str,
) -> None:
    left = Text()
    _append_node_label(left, tree, src, target_hz)
    src_tag = _node_plain_tag(tree, src, target_hz)
    for edge_index, (_, dst) in enumerate(block):
        right = Text()
        _append_node_label(right, tree, dst, target_hz)
        if edge_index == 0:
            _append_edge_line(out, indent="  ", left=left, arrow=" ─┬→ ", right=right)
            continue
        branch = "├→ " if edge_index < len(block) - 1 else "└→ "
        pad = " " * len(src_tag)
        _append_edge_line(out, indent=f"  {pad} ", left=Text(), arrow=branch, right=right)


def render_rich_text_plain(text: Text, *, width: int = 100) -> str:
    """把 Rich Text 收成无 ANSI 的纯文本，便于写入异常消息。"""
    from io import StringIO

    buffer = StringIO()
    Console(
        file=buffer,
        force_terminal=False,
        no_color=True,
        width=width,
        legacy_windows=False,
    ).print(text, end="")
    return buffer.getvalue().rstrip("\n")


def build_component_graph(
    tree: Tree,
    *,
    node_names: frozenset[str] | set[str],
    targets: Sequence[tuple[str, int]],
    heading: str = "时钟连通域",
) -> Text:
    names_set = set(node_names)
    target_hz = dict(targets)
    parents = _collect_parents_in_set(tree, names_set)
    layers = _longest_path_layers(names_set, parents)
    out = Text(f"{heading}\n", style="bold progress.title")

    single_edges: list[tuple[str, str]] = []
    has_fan_in = False
    for dst in sorted(names_set, key=lambda name: (layers.get(name, 0), name)):
        srcs = list(parents.get(dst, ()))
        if len(srcs) > 1:
            has_fan_in = True
            block = [(src, dst) for src in srcs]
            _render_fan_in_block(out, tree, target_hz, block, dst)
        elif len(srcs) == 1:
            single_edges.append((srcs[0], dst))

    if not has_fan_in and not single_edges:
        for name in sorted(names_set):
            line = Text("  ")
            _append_node_label(line, tree, name, target_hz)
            out.append_text(line)
            out.append("\n")
        return out

    single_edges.sort(
        key=lambda item: (layers[item[0]], item[0], layers[item[1]], item[1])
    )
    index = 0
    while index < len(single_edges):
        src, dst = single_edges[index]
        fan_out_end = index + 1
        dst_layer = layers[dst]
        while fan_out_end < len(single_edges):
            next_src, next_dst = single_edges[fan_out_end]
            if next_src != src or layers[next_dst] != dst_layer:
                break
            fan_out_end += 1
        if fan_out_end - index > 1:
            _render_fan_out_block(
                out,
                tree,
                target_hz,
                single_edges[index:fan_out_end],
                src,
            )
            index = fan_out_end
            continue

        left = Text()
        right = Text()
        _append_node_label(left, tree, src, target_hz)
        _append_node_label(right, tree, dst, target_hz)
        _append_edge_line(out, indent="  ", left=left, arrow=" → ", right=right)
        index += 1
    return out


class ProgressSession:
    """Rich 动态进度：大进度条 + 子树小进度 + 连通域有向图。"""

    def __init__(self, tree: Tree | None = None) -> None:
        self._tree = tree
        self._console = Console(
            theme=_THEME,
            stderr=True,
            color_system="truecolor",
            force_terminal=True,
            legacy_windows=False,
        )
        self.enabled = self._console.is_terminal
        self.failed = False
        self._live: Live | None = None
        self._overall: Progress | None = None
        self._overall_task: int | None = None
        self._sub: Progress | None = None
        self._sub_task: int | None = None
        self._overall_total = 1
        self._overall_done = 0
        self._stage_text = "准备"
        self._stage_human = ""
        self._stage_started_at: float | None = None
        self._component_summary: list[str] = []
        self._active_component_index = 0
        self._active_component_total = 0
        self._active_component_clks = ""
        self._active_graph: Text | None = None
        self._sub_visible = False
        self._search_active = False
        self._search_kind = ""
        self._search_phase = ""
        self._search_detail = ""
        self._search_current = 0
        self._search_total = 0
        self._search_progress: Progress | None = None
        self._search_task: int | None = None

    def start(self) -> None:
        if not self.enabled:
            return
        self._overall = Progress(
            SpinnerColumn(),
            TextColumn("[progress.title]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self._console,
            transient=True,
        )
        self._sub = Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(bar_width=32),
            TaskProgressColumn(),
            console=self._console,
            transient=True,
        )
        self._overall_task = self._overall.add_task("pll_mini", total=self._overall_total)
        self.bootstrap_plan()
        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=10,
            transient=True,
            screen=True,
        )
        self._live.start()

    def stop(self) -> None:
        if not self.enabled:
            self._live = None
            self._overall = None
            self._sub = None
            return
        if self._live is not None:
            if (
                not self.failed
                and self._overall is not None
                and self._overall_task is not None
            ):
                self._overall.update(
                    self._overall_task,
                    completed=self._overall_total,
                    description="完成",
                )
                self._refresh()
            self._live.stop()
            self._live = None
        self._overall = None
        self._sub = None
        self._component_summary.clear()
        self._sub_visible = False
        self._active_graph = None
        self._stage_human = ""
        self._stage_started_at = None
        self._clear_search_progress()
        try:
            self._console.clear_live()
        except Exception:
            pass
        self._console.show_cursor(True)

    def halt_for_output(self) -> None:
        """失败诊断等固定输出前结束 Live，避免与 Rich 面板叠行。"""
        self.stop()

    def set_tree(self, tree: Tree) -> None:
        self._tree = tree

    def bootstrap_plan(self) -> None:
        """会话启动时的总步数占位：regmodel + partition + 1 子树 + 后续固定阶段。"""
        self.plan_overall(component_count=1)

    def plan_overall(self, *, component_count: int, extra_steps: int = 7) -> None:
        """partition 之后设置总步数：regmodel、partition、各子树、merge、verify、resolve、config、header。"""
        self._overall_total = max(1, component_count + extra_steps)
        if self._overall is not None and self._overall_task is not None:
            self._overall.update(
                self._overall_task,
                total=self._overall_total,
                completed=self._overall_done,
            )
        self._refresh()

    def advance_overall(self, *, description: str = "", steps: int = 1) -> None:
        self._overall_done = min(self._overall_done + steps, self._overall_total)
        if description:
            self._stage_text = description
        if self._overall is not None and self._overall_task is not None:
            self._overall.update(
                self._overall_task,
                completed=self._overall_done,
                description=description or None,
            )
        self._sub_visible = False
        self._refresh()

    def _set_active_stage(
        self,
        component: str,
        action: str,
        label: str,
        *,
        fields: Mapping[str, object],
        started_at: float,
    ) -> None:
        human = _human_stage_name(component, action, label)
        self._stage_human = human
        self._stage_started_at = started_at
        self._stage_text = human
        if self._overall is not None and self._overall_task is not None:
            self._overall.update(
                self._overall_task,
                description=human,
            )

    def _clear_active_stage(self) -> None:
        self._stage_human = ""
        self._stage_started_at = None

    def stage_start(
        self,
        component: str,
        action: str,
        label: str,
        **fields: object,
    ) -> float:
        started = time.perf_counter()
        self._set_active_stage(component, action, label, fields=fields, started_at=started)
        if component == "diagnose":
            self._sub_visible = False
        elif component == "search" and action == "partition":
            self._sub_visible = False
        elif component == "search" and action == "component" and "progress" not in fields:
            self._begin_component_stage(label, fields)
        self._refresh()
        return started

    def stage_done(
        self,
        component: str,
        action: str,
        label: str,
        started_at: float,
        **fields: object,
    ) -> None:
        failed = bool(fields.get("failed"))
        self._clear_active_stage()
        if failed:
            self.failed = True
            self.halt_for_output()
            return
        if component == "search" and action == "partition":
            count = int(fields.get("components", 0) or 0)
            if count > 0 and self._overall_total <= 1:
                self.plan_overall(component_count=count)
            self.advance_overall(description="分割连通域完成", steps=1)
        elif component == "search" and action == "component":
            progress = str(fields.get("progress", ""))
            status = str(fields.get("status", ""))
            if status == "ok" and progress:
                self._component_summary.append(f"[progress.ok]✓ {progress}[/]")
            self.advance_overall(
                description=f"子树 {label} 完成",
                steps=1,
            )
        elif component == "search" and action == "merge":
            self.advance_overall(description="合并子树模型", steps=1)
        elif component == "search" and action == "solve":
            self.advance_overall(description="时钟树约束求解完成", steps=0)
        elif component == "resolve" and action == "verify":
            self.advance_overall(description="公式回放验证", steps=1)
        elif component == "resolve" and action == "nodes":
            self.advance_overall(description="解析节点频率", steps=1)
        elif component == "models" and action == "load":
            self.advance_overall(description="寄存器模型已加载", steps=1)
        elif component == "resolve" and action == "fit":
            pass
        elif component == "models" and action == "compute":
            if label == "tree_resolve":
                self.advance_overall(description="频率图求解完成", steps=1)
            elif label == "config_plan":
                self.advance_overall(description="配置计划完成", steps=1)
            elif label == "header_regs":
                self.advance_overall(description="头文件寄存器收集完成", steps=1)
        self._refresh()

    def show_partition_preview(
        self,
        tree: Tree,
        components: Sequence[object],
    ) -> None:
        if not self.enabled:
            return
        self._tree = tree
        self._active_component_total = len(components)
        self._component_summary = []
        self.plan_overall(component_count=len(components))
        self._stage_human = f"分割连通域 · {len(components)} 个子树"
        self._stage_text = self._stage_human
        self._refresh()

    def begin_component_search(
        self,
        *,
        kind: str,
        mux_total: int,
        free_muxes: Sequence[str],
    ) -> None:
        if not self.enabled:
            return
        self.end_component_search()
        self._search_active = True
        self._search_kind = kind
        self._search_phase = "准备"
        self._search_detail = ""
        self._search_current = 0
        self._search_total = max(0, mux_total)
        if self._search_progress is None:
            self._search_progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.stage]{task.description}"),
                BarColumn(bar_width=28),
                TaskProgressColumn(),
                console=self._console,
                transient=True,
            )
        label = "PLL 参考路径" if kind == "pll_ref" else "子树求解"
        if mux_total > 0:
            desc = f"{label} · mux枚举 0/{mux_total}"
        else:
            desc = f"{label} · 准备"
        if self._search_task is None:
            self._search_task = self._search_progress.add_task(
                desc,
                total=max(1, mux_total),
                completed=0,
            )
        else:
            self._search_progress.update(
                self._search_task,
                description=desc,
                total=max(1, mux_total),
                completed=0,
            )
        mux_hint = ",".join(free_muxes[:3])
        if len(free_muxes) > 3:
            mux_hint = f"{mux_hint},…"
        if mux_hint:
            self._search_detail = f"自由 mux: {mux_hint}"
        self._refresh()

    def tick_component_search(
        self,
        phase: str,
        *,
        current: int | None = None,
        total: int | None = None,
        detail: str = "",
        force: bool = False,
    ) -> None:
        if not self.enabled or not self._search_active:
            return
        self._search_phase = phase
        if detail or force:
            self._search_detail = detail
        if current is not None:
            self._search_current = current
        if total is not None and total > 0:
            self._search_total = total
        if self._search_progress is None or self._search_task is None:
            self._refresh()
            return
        label = "PLL 参考路径" if self._search_kind == "pll_ref" else "子树求解"
        suffix = ""
        if self._search_detail:
            detail = self._search_detail
            if len(detail) > 96:
                detail = f"{detail[:93]}..."
            suffix = f" · {detail}"
        if self._search_total > 0 and current is not None:
            desc = f"{label} · {phase} {current}/{self._search_total}{suffix}"
            self._search_progress.update(
                self._search_task,
                description=desc,
                completed=current,
                total=self._search_total,
            )
        else:
            desc = f"{label} · {phase}{suffix}"
            self._search_progress.update(
                self._search_task,
                description=desc,
                completed=0,
                total=1,
            )
        self._refresh()

    def end_component_search(self) -> None:
        self._search_active = False
        self._search_phase = ""
        self._search_detail = ""
        self._search_current = 0
        self._search_total = 0
        if self._search_progress is not None and self._search_task is not None:
            self._search_progress.update(
                self._search_task,
                description="",
                completed=0,
                total=1,
            )
        self._refresh()

    def _clear_search_progress(self) -> None:
        self._search_active = False
        self._search_phase = ""
        self._search_detail = ""
        self._search_current = 0
        self._search_total = 0
        self._search_progress = None
        self._search_task = None

    def show_active_component(self, tree: Tree, component: object) -> None:
        if not self.enabled:
            return
        self.end_component_search()
        self._tree = tree
        index = int(getattr(component, "index", 0))
        total = int(getattr(component, "total", 0))
        targets = tuple(getattr(component, "targets", ()))
        node_names = getattr(component, "node_names", frozenset())
        clks = ",".join(name for name, _ in targets)
        self._active_component_index = index
        self._active_component_total = total
        self._active_component_clks = clks
        self._active_graph = build_component_graph(
            tree,
            node_names=node_names,
            targets=targets,
        )
        self._sub_visible = True
        if self._sub is not None and self._sub_task is not None:
            self._sub.update(
                self._sub_task,
                description=f"子树 {index}/{total} · {clks}",
                completed=index - 1,
                total=total,
            )
        elif self._sub is not None:
            self._sub_task = self._sub.add_task(
                f"子树 {index}/{total} · {clks}",
                total=total,
                completed=index - 1,
            )
        self._refresh()

    def _begin_component_stage(self, label: str, fields: Mapping[str, object]) -> None:
        self._sub_visible = True
        if self._sub is not None:
            total = self._active_component_total or 1
            try:
                index = int(str(label).split("/")[0])
            except (IndexError, ValueError):
                index = 0
            clks = str(fields.get("clks", ""))
            desc = f"子树 {label}"
            if clks:
                desc = f"{desc} · {clks}"
            stats = (
                f"nodes={fields.get('nodes')} "
                f"mux={fields.get('free_mux')} "
                f"div={fields.get('free_div')} "
                f"anchors={fields.get('anchors')} "
                f"port_anchors={fields.get('port_anchors')}"
            )
            desc = f"{desc} | {stats}"
            if self._sub_task is None:
                self._sub_task = self._sub.add_task(
                    desc,
                    total=total,
                    completed=max(0, index - 1),
                )
            else:
                self._sub.update(
                    self._sub_task,
                    description=desc,
                    total=total,
                    completed=max(0, index - 1),
                )

    def _render(self) -> Group:
        parts: list[object] = []
        if self._overall is not None:
            parts.append(
                Panel(
                    self._overall,
                    title="[progress.title]pll_mini[/]",
                    border_style="progress.title",
                    padding=(0, 1),
                )
            )
        if self._sub_visible and self._sub is not None:
            body: list[object] = [self._sub]
            if self._search_active and self._search_progress is not None:
                body.append(self._search_progress)
            if self._active_graph is not None:
                body.append(self._active_graph)
            parts.append(
                Panel(
                    Group(*body),
                    title=(
                        f"[progress.title]子树 "
                        f"{self._active_component_index}/"
                        f"{self._active_component_total}[/]"
                    ),
                    border_style="progress.clk",
                    padding=(0, 1),
                )
            )
        elif self._component_summary:
            parts.append(
                Panel(
                    "\n".join(self._component_summary),
                    title="[progress.title]连通域[/]",
                    border_style="progress.dim",
                    padding=(0, 1),
                )
            )
        return Group(*parts)

    def _refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._render())


@contextmanager
def pll_mini_progress(tree: Tree | None = None) -> Iterator[ProgressSession]:
    session = ProgressSession(tree=tree)
    _set_active_session(session)
    try:
        session.start()
        yield session
    finally:
        if not session.failed:
            session.stop()
        _set_active_session(None)
