from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator


@contextmanager
def node_context(node, stage: str) -> Iterator[None]:
    """在插件调用失败时保留阶段、节点名及原始异常。"""
    try:
        yield
    except Exception as exc:
        error_type = (
            ValueError
            if isinstance(exc, (ValueError, TypeError, KeyError, ArithmeticError))
            else RuntimeError
        )
        raise error_type(
            f"[{stage}] nodes[{node.name!r}] kind={node.kind}: {exc}"
        ) from exc


def graph_context(tree) -> str:
    """列出全图失败的求解范围，不把工具错误归罪于单个节点。"""
    return f"nodes={list(tree.nodes)!r}"
