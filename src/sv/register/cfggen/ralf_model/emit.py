from __future__ import annotations

from ralf_model.nodes import BlockNode, FieldNode, RalfDocument, RegisterNode, SystemNode


def _fmt_at_int(v: int) -> str:
    """`@` 后的偏移（字节或位），采用 Verilog 无尺寸十六进制字面量。"""
    if v < 0:
        return str(v)
    return f"'h{v:x}"


def _emit_field(f: FieldNode, indent: str) -> list[str]:
    head = f"{indent}field {f.name}"
    if f.paren_path is not None:
        head += f"({f.paren_path})"
    if f.offset_bits is not None:
        head += f" @{_fmt_at_int(f.offset_bits)}"
    head += " {"
    lines = [head]
    inner = indent + "  "
    for stmt in f.inner_statements:
        for line in stmt.splitlines():
            lines.append(f"{inner}{line.strip()}")
    lines.append(indent + "}")
    return lines


def _emit_register(r: RegisterNode, indent: str) -> list[str]:
    head = f"{indent}register {r.name}"
    if r.paren_path is not None:
        head += f" ({r.paren_path})"
    if r.offset_bytes is not None:
        head += f" @{_fmt_at_int(r.offset_bytes)}"
    if r.declaration_only:
        return [f"{head};"]
    lines = [head + " {"]
    inner = indent + "  "
    if r.bytes_width is not None:
        lines.append(f"{inner}bytes {r.bytes_width};")
    for f in r.fields:
        lines.extend(_emit_field(f, inner))
    lines.append(indent + "}")
    return lines


def _emit_block_open_line(b: BlockNode, indent: str) -> str:
    """``block ...`` 行中 `{` 之前的部分（含 `@` / `=` 等）。"""
    line = f"{indent}block {b.name}"
    if b.rhs_head is not None:
        line += f" = {b.rhs_head}"
        if b.rhs_paren_path is not None:
            line += f" ({b.rhs_paren_path})"
    elif b.rhs_paren_path is not None:
        line += f" ({b.rhs_paren_path})"
    if b.base_address is not None:
        line += f" @{_fmt_at_int(b.base_address)}"
    return line


def _emit_system_open_line(s: SystemNode, indent: str) -> str:
    line = f"{indent}system {s.name}"
    if s.rhs_head is not None:
        line += f" = {s.rhs_head}"
        if s.rhs_paren_path is not None:
            line += f" ({s.rhs_paren_path})"
    elif s.rhs_paren_path is not None:
        line += f" ({s.rhs_paren_path})"
    if s.base_address is not None:
        line += f" @{_fmt_at_int(s.base_address)}"
    return line


def _emit_system(s: SystemNode, indent: str) -> list[str]:
    head_line = _emit_system_open_line(s, indent)
    if not s.has_body:
        return [f"{head_line};"]
    lines = [head_line + " {"]
    inner = indent + "  "
    if s.bytes_width is not None:
        lines.append(f"{inner}bytes {s.bytes_width};")
    for sub in s.systems:
        lines.extend(_emit_system(sub, inner))
    for sub in s.blocks:
        lines.extend(_emit_block(sub, inner))
    lines.append(indent + "}")
    return lines


def _emit_block(b: BlockNode, indent: str) -> list[str]:
    head_line = _emit_block_open_line(b, indent)
    if not b.has_body:
        return [f"{head_line};"]
    lines = [head_line + " {"]
    inner = indent + "  "
    if b.bytes_width is not None:
        lines.append(f"{inner}bytes {b.bytes_width};")
    for r in b.registers:
        lines.extend(_emit_register(r, inner))
    for sub in b.blocks:
        lines.extend(_emit_block(sub, inner))
    lines.append(indent + "}")
    return lines


def dump_ralf(doc: RalfDocument) -> str:
    """将 `RalfDocument` 序列化为 RALF 源文本（规范化排版）。"""
    out: list[str] = []
    first = True
    for s in doc.systems:
        if not first:
            out.append("")
        first = False
        out.extend(_emit_system(s, ""))
    for b in doc.blocks:
        if not first:
            out.append("")
        first = False
        out.extend(_emit_block(b, ""))
    return "\n".join(out) + ("\n" if out else "")
