from __future__ import annotations

from typing import Sequence

from rich.console import Console
from rich.text import Text

from model.freq_graph import parent_port_for_child
from model.nodes import ClkNode, DivNode, MuxNode, PllNode, Tree, parse_source_endpoint


def rich_console_kwargs() -> dict[str, object]:
    return {
        "stderr": True,
        "color_system": None,
        "no_color": True,
        "legacy_windows": False,
    }


def _hz_mhz(hz: int) -> str:
    if hz % 1_000_000 == 0:
        return f"{hz // 1_000_000} MHz"
    if hz % 1_000 == 0:
        return f"{hz / 1_000:.3f} kHz"
    return f"{hz} Hz"


def _pll_display_freq(node: PllNode) -> int | None:
    return node.freq_for_group(node.primary_output_group)


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
    parents: dict[str, tuple[str, ...]],
) -> dict[str, int]:
    layers = {name: 0 for name in names_set}
    for _ in range(len(names_set)):
        changed = False
        for name in names_set:
            for parent in parents.get(name, ()):
                candidate = layers[parent] + 1
                if candidate > layers[name]:
                    layers[name] = candidate
                    changed = True
        if not changed:
            break
    return layers


def _node_plain_tag(
    tree: Tree,
    name: str,
    target_hz: dict[str, int],
) -> str:
    node = tree.nodes[name]
    kind = getattr(node, "kind", "?")
    if isinstance(node, DivNode):
        kind = node.div_kind
    parts = [name, f"[{kind}]"]
    if name in target_hz:
        parts.append(f"target={_hz_mhz(target_hz[name])}")
    elif isinstance(node, ClkNode) and node.freq is not None and node.freq > 0:
        parts.append(f"target={_hz_mhz(node.freq)}")
    elif isinstance(node, PllNode) and (pll_hz := _pll_display_freq(node)) is not None and pll_hz > 0:
        parts.append(f"target={_hz_mhz(pll_hz)}")
    elif isinstance(node, DivNode) and node.ratio is not None:
        parts.append(f"ratio={node.ratio}")
    elif isinstance(node, MuxNode) and node.sel is not None:
        parts.append(f"sel={node.sel}")
    return " ".join(parts)


def render_rich_text_plain(text: Text, *, width: int = 100) -> str:
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
    out = Text(f"{heading}\n")

    for name in sorted(names_set, key=lambda item: (layers.get(item, 0), item)):
        srcs = parents.get(name, ())
        node_tag = _node_plain_tag(tree, name, target_hz)
        if not srcs:
            out.append(f"  {node_tag}\n")
            continue
        for src in srcs:
            src_tag = _node_plain_tag(tree, src, target_hz)
            out.append(f"  {src_tag} -> {node_tag}\n")
    return out
