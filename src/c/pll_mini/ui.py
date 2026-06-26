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
from rich.tree import Tree as RichTree

from freq_model import parent_port_for_child
from nodes import ClkNode, DivNode, MuxNode, PllNode, Tree, parse_source_endpoint

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


def _format_fields(fields: Mapping[str, object]) -> str:
    if not fields:
        return ""
    return " · ".join(f"{key}={value}" for key, value in fields.items())


def _downstream_children_in_set(
    tree: Tree,
    name: str,
    names_set: set[str],
) -> list[str]:
    children: list[str] = []
    for other_name in names_set:
        if other_name == name:
            continue
        other = tree.nodes[other_name]
        if other.kind == "source":
            continue
        if isinstance(other, MuxNode):
            for arm in other.source.values():
                arm_name, _ = parse_source_endpoint(arm, ctx="child")
                if arm_name == name:
                    children.append(other_name)
            continue
        try:
            parent = parent_port_for_child(tree, other_name)
        except ValueError:
            continue
        if parent.node == name:
            children.append(other_name)
    return sorted(children)


def _component_roots(tree: Tree, names_set: set[str]) -> list[str]:
    roots: list[str] = []
    for name in sorted(names_set):
        node = tree.nodes[name]
        if node.kind == "source":
            roots.append(name)
            continue
        try:
            parent = parent_port_for_child(tree, name)
            parent_name = parent.node
        except ValueError:
            roots.append(name)
            continue
        if parent_name not in names_set:
            roots.append(name)
    if not roots:
        return sorted(names_set)[:1]
    return sorted(dict.fromkeys(roots))


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
    elif isinstance(node, ClkNode) and node.freq > 0:
        label.append(f" → {_hz_mhz(node.freq)}", style="tree.target")
    elif isinstance(node, PllNode) and node.freq is not None and node.freq > 0:
        label.append(f" → {_hz_mhz(node.freq)}", style="tree.target")
    elif isinstance(node, DivNode) and node.ratio is not None:
        label.append(f" ratio={node.ratio}", style="tree.target")
    elif isinstance(node, MuxNode) and node.sel is not None:
        label.append(f" sel={node.sel}", style="tree.target")
    return label


def build_component_subtree(
    tree: Tree,
    *,
    node_names: frozenset[str] | set[str],
    targets: Sequence[tuple[str, int]],
) -> RichTree:
    names_set = set(node_names)
    target_hz = dict(targets)
    rich_root = RichTree(Text("时钟连通域", style="bold progress.title"), guide_style="progress.dim")
    seen: set[str] = set()

    def attach(parent: RichTree, name: str) -> None:
        if name in seen:
            return
        seen.add(name)
        branch = parent.add(_node_tree_label(tree, name, target_hz))
        for child in _downstream_children_in_set(tree, name, names_set):
            attach(branch, child)

    for root in _component_roots(tree, names_set):
        attach(rich_root, root)
    for orphan in sorted(names_set - seen):
        attach(rich_root, orphan)
    return rich_root


class ProgressSession:
    """Rich 动态进度：大进度条 + 子树小进度 + 连通域树图。"""

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
        self._stage_fields = ""
        self._component_summary: list[str] = []
        self._active_component_index = 0
        self._active_component_total = 0
        self._active_component_clks = ""
        self._active_subtree: RichTree | None = None
        self._sub_visible = False

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
        )
        self._live.start()

    def stop(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None
        self._overall = None
        self._sub = None

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

    def stage_start(
        self,
        component: str,
        action: str,
        label: str,
        **fields: object,
    ) -> float:
        started = time.perf_counter()
        self._stage_text = f"{component} · {action} · {label}"
        self._stage_fields = _format_fields(fields)
        if component == "models" and action == "load":
            if self._overall is not None and self._overall_task is not None:
                self._overall.update(
                    self._overall_task,
                    description="加载寄存器模型",
                )
        elif component == "consolver" and action == "solve":
            if self._overall is not None and self._overall_task is not None:
                self._overall.update(
                    self._overall_task,
                    description="SMT 约束求解",
                )
        elif component == "diagnose":
            self._sub_visible = False
        elif component == "search" and action == "solve":
            if self._overall is not None and self._overall_task is not None:
                self._overall.update(
                    self._overall_task,
                    description="时钟树约束求解",
                )
        elif component == "search" and action == "partition":
            self._sub_visible = False
            if self._overall is not None and self._overall_task is not None:
                self._overall.update(
                    self._overall_task,
                    description="分割连通域",
                )
        elif action == "component" and "progress" not in fields:
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
        _ = started_at
        if fields.get("failed"):
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
            self.advance_overall(description="寄存器模型就绪", steps=1)
        elif component == "models" and action == "compute":
            if label == "config_plan":
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
        self._stage_text = f"search · partition · {len(components)} 个子树"
        self._refresh()

    def show_active_component(self, tree: Tree, component: object) -> None:
        if not self.enabled:
            return
        self._tree = tree
        index = int(getattr(component, "index", 0))
        total = int(getattr(component, "total", 0))
        targets = tuple(getattr(component, "targets", ()))
        node_names = getattr(component, "node_names", frozenset())
        clks = ",".join(name for name, _ in targets)
        self._active_component_index = index
        self._active_component_total = total
        self._active_component_clks = clks
        self._active_subtree = build_component_subtree(
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
        self._stage_text = f"search · component · {index}/{total}"
        self._stage_fields = f"clks={clks} · nodes={len(node_names)}"
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
            if self._active_subtree is not None:
                body.append(self._active_subtree)
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
        stage_line = self._stage_text
        if self._stage_fields:
            stage_line = f"{stage_line}  [progress.dim]{self._stage_fields}[/]"
        parts.append(Text.from_markup(stage_line, style="progress.stage"))
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
