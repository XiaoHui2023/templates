from __future__ import annotations


def safe_name(raw: str) -> str:
    """编码符号中的特殊字符，避免不同配置名发生碰撞。"""
    if raw and all(ch.isascii() and (ch.isalnum() or ch in "_$") for ch in raw):
        return raw
    return "encoded__" + raw.encode("utf-8").hex()


def act(node: str) -> str:
    """返回节点有效状态符号。"""
    return symbol("act", node)


def freq(port) -> str:
    """返回输出频率符号。"""
    return symbol("freq", port.node, port.group)


def symbol(namespace: str, *parts: str) -> str:
    """使用带长度的分量构造符号，区分节点名和端口名中的分隔符。"""
    encoded = [part.encode("utf-8").hex() for part in parts]
    return namespace + "__" + "__".join(f"{len(part)}_{part}" for part in encoded)


def port_suffix(port) -> str:
    """返回约束标签中的输出名称。"""
    return port.group or "out"
