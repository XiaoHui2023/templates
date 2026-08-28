from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from ralf_model.errors import RalfParseError
from ralf_model.nodes import BlockNode, FieldNode, RalfDocument, RegisterNode, SystemNode


class _Parser:
    def __init__(
        self,
        text: str,
        *,
        path: Path | None = None,
        line_origins: Sequence[tuple[Path, int]] | None = None,
    ) -> None:
        self._s = text
        self._n = len(text)
        self._i = 0
        self.line = 1
        self.col = 1
        self._path = path
        self._line_origins = line_origins

    def _advance(self, n: int = 1) -> None:
        for _ in range(n):
            if self._i >= self._n:
                return
            if self._s[self._i] == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1
            self._i += 1

    def _peek(self, offset: int = 0) -> str | None:
        j = self._i + offset
        return self._s[j] if j < self._n else None

    def _error_location(self) -> tuple[Path | None, int]:
        path = self._path
        line = self.line
        if self._line_origins and 0 < self.line <= len(self._line_origins):
            path, line = self._line_origins[self.line - 1]
        return path, line

    def _error(self, msg: str) -> None:
        path, line = self._error_location()
        raise RalfParseError(msg, line=line, col=self.col, path=path)

    def skip_ws_and_comments(self) -> None:
        while self._i < self._n:
            c = self._s[self._i]
            if c in " \t\r\n":
                self._advance()
            elif c == "/" and self._peek(1) == "/":
                while self._i < self._n and self._s[self._i] != "\n":
                    self._advance()
            elif c == "/" and self._peek(1) == "*":
                self._advance(2)
                while self._i + 1 < self._n and not (
                    self._s[self._i] == "*" and self._s[self._i + 1] == "/"
                ):
                    self._advance()
                if self._i + 1 < self._n:
                    self._advance(2)
                else:
                    self._error("未闭合的块注释")
            else:
                break

    def expect_char(self, ch: str) -> None:
        self.skip_ws_and_comments()
        if self._peek() != ch:
            self._error(f"期望 {ch!r}，实际为 {self._peek()!r}")
        self._advance()

    def expect_keyword(self, kw: str) -> None:
        self.skip_ws_and_comments()
        start = self._i
        ident = self._read_ident_raw()
        if ident is None or ident.lower() != kw.lower():
            self._i = start
            self._error(f"期望关键字 {kw!r}")

    def _read_ident_raw(self) -> str | None:
        if self._i >= self._n:
            return None
        c = self._s[self._i]
        if not (c.isalpha() or c == "_"):
            return None
        start = self._i
        self._advance()
        while self._i < self._n:
            c2 = self._s[self._i]
            if c2.isalnum() or c2 == "_":
                self._advance()
            else:
                break
        return self._s[start : self._i]

    def read_ident(self) -> str:
        self.skip_ws_and_comments()
        ident = self._read_ident_raw()
        if ident is None:
            self._error("期望标识符")
        return ident

    def parse_integer_value(self) -> int:
        self.skip_ws_and_comments()
        v, end = _parse_int_literal(self._s, self._i)
        if end == self._i:
            self._error("期望整数字面量")
        while self._i < end:
            self._advance()
        return v

    def read_braced_block(self) -> str:
        """从当前位置的 `{` 起读取一对花括号（含外侧花括号）。"""
        self.skip_ws_and_comments()
        if self._peek() != "{":
            self._error("期望 {")
        start = self._i
        depth = 0
        i = self._i
        while i < self._n:
            c = self._s[i]
            if c == "/" and i + 1 < self._n and self._s[i + 1] == "/":
                while i < self._n and self._s[i] != "\n":
                    i += 1
                continue
            if c == "/" and i + 1 < self._n and self._s[i + 1] == "*":
                i += 2
                while i + 1 < self._n and not (
                    self._s[i] == "*" and self._s[i + 1] == "/"
                ):
                    i += 1
                i = min(i + 2, self._n)
                continue
            if c == "{":
                depth += 1
                i += 1
            elif c == "}":
                depth -= 1
                i += 1
                if depth == 0:
                    span = self._s[start:i]
                    while self._i < i:
                        self._advance()
                    return span
                continue
            else:
                i += 1
        self._error("未闭合的 {")

    def read_until_semicolon(self) -> str:
        """从当前位置读到（不含）`;`，并消费分号。不跨入注释外的换行可简化处理。"""
        self.skip_ws_and_comments()
        start = self._i
        while self._i < self._n:
            c = self._s[self._i]
            if c == "/" and self._peek(1) == "/":
                self._error("行内值不应含注释")
            if c == ";":
                text = self._s[start : self._i].strip()
                self._advance()
                return text
            if c == "\n":
                pass  # allow multiline for complex expressions
            self._advance()
        self._error("期望 ;")

    def parse_document(self) -> RalfDocument:
        systems: list[SystemNode] = []
        blocks: list[BlockNode] = []
        self.skip_ws_and_comments()
        while self._i < self._n:
            kw = self._peek_keyword()
            if kw == "system":
                systems.append(self.parse_system())
            elif kw == "block":
                blocks.append(self.parse_block())
            else:
                self._error(f"顶层期望 system 或 block，得到 {kw!r}")
            self.skip_ws_and_comments()
        return RalfDocument(systems=systems, blocks=blocks)

    def _peek_keyword(self) -> str:
        self.skip_ws_and_comments()
        save = self._i
        ident = self._read_ident_raw()
        self._i = save
        return ident.lower() if ident else ""

    def read_hierarchical_block_name(self) -> str:
        """实例名：允许段 `ident`、`.` 分层以及后缀 `[ ... ]`（如 `blk_vh[2]`、`dom[*]`）。"""
        name = self.read_ident()
        while True:
            self.skip_ws_and_comments()
            if self._peek() == "[":
                name += self.read_balanced_square_brackets()
                continue
            if self._peek() == ".":
                self._advance()
                name += "." + self.read_ident()
                continue
            break
        return name

    def read_balanced_square_brackets(self) -> str:
        """从当前 `[` 读到匹配的 `]`（含括号），并前进游标。"""
        if self._peek() != "[":
            self._error("期望 [")
        start = self._i
        depth = 0
        i = self._i
        while i < self._n:
            c = self._s[i]
            if c == "[":
                depth += 1
                i += 1
            elif c == "]":
                depth -= 1
                i += 1
                if depth == 0:
                    span = self._s[start:i]
                    while self._i < i:
                        self._advance()
                    return span
            else:
                i += 1
        self._error("未闭合的 [")

    def read_round_paren_inner(self) -> str:
        """读取一对圆括号内的文本（含嵌套括号），游标停在闭合 `)` 之后。"""
        self.skip_ws_and_comments()
        self.expect_char("(")
        start = self._i
        depth = 1
        while self._i < self._n and depth:
            c = self._s[self._i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    inner = self._s[start : self._i].strip()
                    self._advance()
                    return inner
            self._advance()
        self._error("未闭合的 (")

    def parse_block_rhs_after_equals(
        self,
    ) -> tuple[str, str | None, int | None]:
        """解析 ``=`` 之后：``层级名 [ (路径) ] [ @地址 ]``，止于 ``;`` 或 ``{{`` 之前。"""
        head = self.read_hierarchical_block_name()
        self.skip_ws_and_comments()
        paren_inner: str | None = None
        if self._peek() == "(":
            paren_inner = self.read_round_paren_inner()
            self.skip_ws_and_comments()
        addr: int | None = None
        if self._peek() == "@":
            self._advance()
            addr = self.parse_integer_value()
            self.skip_ws_and_comments()
        return head, paren_inner, addr

    def parse_system(self) -> SystemNode:
        self.expect_keyword("system")
        name = self.read_hierarchical_block_name()
        self.skip_ws_and_comments()

        name_paren: str | None = None
        if self._peek() == "(":
            name_paren = self.read_round_paren_inner()
            self.skip_ws_and_comments()

        if self._peek() == "@":
            self._advance()
            addr = self.parse_integer_value()
            self.skip_ws_and_comments()
            if self._peek() == ";":
                self._advance()
                return SystemNode(
                    name=name,
                    rhs_paren_path=name_paren,
                    base_address=addr,
                    has_body=False,
                    systems=[],
                    blocks=[],
                )
            if self._peek() == "{":
                self._advance()
                bw, subs_sys, subs_blk = self._parse_system_body()
                self.expect_char("}")
                return SystemNode(
                    name=name,
                    rhs_paren_path=name_paren,
                    base_address=addr,
                    has_body=True,
                    bytes_width=bw,
                    systems=subs_sys,
                    blocks=subs_blk,
                )
            self._error("system @地址 之后应为 ; 或 {")

        if self._peek() == "=":
            if name_paren is not None:
                self._error("system 名后 `(路径)` 与 `=` 实例化不能同时使用")
            self._advance()
            self.skip_ws_and_comments()
            rhs_head, rhs_path, addr_rhs = self.parse_block_rhs_after_equals()
            self.skip_ws_and_comments()
            if self._peek() == ";":
                self._advance()
                return SystemNode(
                    name=name,
                    rhs_head=rhs_head,
                    rhs_paren_path=rhs_path,
                    base_address=addr_rhs,
                    has_body=False,
                    systems=[],
                    blocks=[],
                )
            if self._peek() == "{":
                self._advance()
                bw, subs_sys, subs_blk = self._parse_system_body()
                self.expect_char("}")
                return SystemNode(
                    name=name,
                    rhs_head=rhs_head,
                    rhs_paren_path=rhs_path,
                    base_address=addr_rhs,
                    has_body=True,
                    bytes_width=bw,
                    systems=subs_sys,
                    blocks=subs_blk,
                )
            self._error("system ... = ... 之后应为 ; 或 {")

        if self._peek() == "{":
            self._advance()
            bw, subs_sys, subs_blk = self._parse_system_body()
            self.expect_char("}")
            return SystemNode(
                name=name,
                rhs_paren_path=name_paren,
                has_body=True,
                bytes_width=bw,
                systems=subs_sys,
                blocks=subs_blk,
            )
        self._error("system 名称之后应为 `(路径)`、`@`、`=` 或 `{")

    def _parse_system_body(
        self,
    ) -> tuple[int | None, list[SystemNode], list[BlockNode]]:
        bw: int | None = None
        subs_sys: list[SystemNode] = []
        subs_blk: list[BlockNode] = []
        while True:
            self.skip_ws_and_comments()
            if self._peek() == "}":
                break
            kw = self._peek_keyword()
            if kw == "bytes":
                self.expect_keyword("bytes")
                bw = self.parse_integer_value()
                self.expect_char(";")
            elif kw == "system":
                subs_sys.append(self.parse_system())
            elif kw == "block":
                subs_blk.append(self.parse_block())
            else:
                self._error(f"system 内出现未识别的内容 {kw!r}")
        return bw, subs_sys, subs_blk

    def parse_block(self) -> BlockNode:
        self.expect_keyword("block")
        name = self.read_hierarchical_block_name()
        self.skip_ws_and_comments()

        name_paren: str | None = None
        if self._peek() == "(":
            name_paren = self.read_round_paren_inner()
            self.skip_ws_and_comments()

        if self._peek() == "@":
            self._advance()
            addr = self.parse_integer_value()
            self.skip_ws_and_comments()
            if self._peek() == ";":
                self._advance()
                return BlockNode(
                    name=name,
                    rhs_paren_path=name_paren,
                    base_address=addr,
                    has_body=False,
                    registers=[],
                    blocks=[],
                )
            if self._peek() == "{":
                self._advance()
                bw, regs, subs = self._parse_block_body()
                self.expect_char("}")
                return BlockNode(
                    name=name,
                    rhs_paren_path=name_paren,
                    base_address=addr,
                    has_body=True,
                    bytes_width=bw,
                    registers=regs,
                    blocks=subs,
                )
            self._error("block @地址 之后应为 ; 或 {")

        if self._peek() == "=":
            if name_paren is not None:
                self._error("block 名后 `(路径)` 与 `=` 实例化不能同时使用")
            self._advance()
            self.skip_ws_and_comments()
            rhs_head, rhs_path, addr_rhs = self.parse_block_rhs_after_equals()
            self.skip_ws_and_comments()
            if self._peek() == ";":
                self._advance()
                return BlockNode(
                    name=name,
                    rhs_head=rhs_head,
                    rhs_paren_path=rhs_path,
                    base_address=addr_rhs,
                    has_body=False,
                    registers=[],
                    blocks=[],
                )
            if self._peek() == "{":
                self._advance()
                bw, regs, subs = self._parse_block_body()
                self.expect_char("}")
                return BlockNode(
                    name=name,
                    rhs_head=rhs_head,
                    rhs_paren_path=rhs_path,
                    base_address=addr_rhs,
                    has_body=True,
                    bytes_width=bw,
                    registers=regs,
                    blocks=subs,
                )
            self._error("block ... = ... 之后应为 ; 或 {")

        if self._peek() == "{":
            self._advance()
            bw, regs, subs = self._parse_block_body()
            self.expect_char("}")
            return BlockNode(
                name=name,
                rhs_paren_path=name_paren,
                has_body=True,
                bytes_width=bw,
                registers=regs,
                blocks=subs,
            )
        self._error("block 名称之后应为 `(路径)`、`@`、`=` 或 `{`")

    def _parse_block_body(self) -> tuple[int | None, list[RegisterNode], list[BlockNode]]:
        bw: int | None = None
        regs: list[RegisterNode] = []
        subs: list[BlockNode] = []
        while True:
            self.skip_ws_and_comments()
            if self._peek() == "}":
                break
            kw = self._peek_keyword()
            if kw == "bytes":
                self.expect_keyword("bytes")
                bw = self.parse_integer_value()
                self.expect_char(";")
            elif kw == "register":
                regs.append(self.parse_register())
            elif kw == "block":
                subs.append(self.parse_block())
            else:
                self._error(f"block 内出现未识别的内容 {kw!r}")
        return bw, regs, subs

    def parse_register(self) -> RegisterNode:
        self.expect_keyword("register")
        name = self.read_ident()
        self.skip_ws_and_comments()
        paren_path: str | None = None
        if self._peek() == "(":
            paren_path = self.read_round_paren_inner()
            self.skip_ws_and_comments()
        offset: int | None = None
        if self._peek() == "@":
            self._advance()
            offset = self.parse_integer_value()
        self.skip_ws_and_comments()
        if self._peek() == ";":
            self._advance()
            return RegisterNode(
                name=name,
                paren_path=paren_path,
                offset_bytes=offset,
                declaration_only=True,
            )
        if self._peek() == "{":
            self._advance()
            rbw, fields = self._parse_register_body()
            self.expect_char("}")
            return RegisterNode(
                name=name,
                paren_path=paren_path,
                offset_bytes=offset,
                bytes_width=rbw,
                fields=fields,
                declaration_only=False,
            )
        self._error("register 后应为 ; 或 {")

    def _parse_register_body(self) -> tuple[int | None, list[FieldNode]]:
        rbw: int | None = None
        fields: list[FieldNode] = []
        while True:
            self.skip_ws_and_comments()
            if self._peek() == "}":
                break
            kw = self._peek_keyword()
            if kw == "bytes":
                self.expect_keyword("bytes")
                rbw = self.parse_integer_value()
                self.expect_char(";")
            elif kw == "field":
                fields.append(self.parse_field())
            else:
                self._error(f"register 体内期望 field 或 bytes，得到 {kw!r}")
        return rbw, fields

    def parse_field(self) -> FieldNode:
        self.expect_keyword("field")
        name = self.read_ident()
        self.skip_ws_and_comments()
        paren_path: str | None = None
        if self._peek() == "(":
            paren_path = self.read_round_paren_inner()
            self.skip_ws_and_comments()
        off_bits: int | None = None
        if self._peek() == "@":
            self._advance()
            off_bits = self.parse_integer_value()
        self.expect_char("{")
        fn = self._parse_field_body()
        self.expect_char("}")
        return fn.model_copy(
            update={"name": name, "paren_path": paren_path, "offset_bits": off_bits}
        )

    def _parse_field_body(self) -> FieldNode:
        inner: list[str] = []

        while True:
            self.skip_ws_and_comments()
            if self._peek() == "}":
                break
            kw = self._peek_keyword()
            if kw == "bits":
                self.expect_keyword("bits")
                bits = self.parse_integer_value()
                self.expect_char(";")
                inner.append(f"bits {bits};")
            elif kw == "reset":
                self.expect_keyword("reset")
                reset = self.read_until_semicolon()
                inner.append(f"reset {reset};")
            elif kw == "access":
                self.expect_keyword("access")
                acc = self.read_ident()
                self.expect_char(";")
                inner.append(f"access {acc};")
            elif kw == "volatile":
                self.expect_keyword("volatile")
                self.skip_ws_and_comments()
                if self._peek() == ";":
                    self._advance()
                    inner.append("volatile;")
                else:
                    vol = self.read_ident()
                    self.expect_char(";")
                    inner.append(f"volatile {vol};")
            else:
                inner.append(self._parse_field_raw_statement())

        return FieldNode(name="__tmp__", inner_statements=inner)

    def _parse_field_raw_statement(self) -> str:
        """解析 field 内未知关键字开头的整句，保留原文用于回写。"""
        self.skip_ws_and_comments()
        head = self.read_ident()
        self.skip_ws_and_comments()
        if self._peek() == "{":
            brace = self.read_braced_block()
            self.skip_ws_and_comments()
            self.expect_char(";")
            return f"{head} {brace};"
        rest = self.read_until_semicolon()
        if rest:
            return f"{head} {rest};"
        return f"{head};"


def _parse_int_literal(s: str, start: int) -> tuple[int, int]:
    """自 `start` 起解析 Verilog 风格整数，返回 (值, 结束下标)。"""
    n = len(s)
    i = start
    while i < n and s[i] in " \t\r\n":
        i += 1
    if i >= n:
        return 0, start
    j = i
    if s[i] == "'":
        return _parse_verilog_unsized(s, i)
    # decimal width? digits then '
    k = i
    while k < n and s[k].isdigit():
        k += 1
    if k < n and s[k] == "'":
        return _parse_verilog_sized(s, i)
    # plain decimal
    if s[i].isdigit():
        while j < n and s[j].isdigit():
            j += 1
        return int(s[i:j]), j
    return 0, start


def _parse_verilog_unsized(s: str, i: int) -> tuple[int, int]:
    """如 'hFF"""
    n = len(s)
    if i >= n or s[i] != "'":
        return 0, i
    i += 1
    if i >= n:
        return 0, i
    base_ch = s[i].lower()
    i += 1
    if i < n and s[i] in "sS":
        i += 1
    while i < n and s[i] in " \t":
        i += 1
    start_digits = i
    while i < n:
        c = s[i]
        if c == "_" or c.isalnum() or c in "?xzXZ":
            i += 1
        else:
            break
    digits = s[start_digits:i].replace("_", "")
    if not digits:
        return 0, start_digits
    if base_ch == "h":
        return int(digits, 16), i
    if base_ch in ("d",):
        return int(digits, 10), i
    if base_ch == "b":
        return int(digits.replace("?", "0").replace("z", "0").replace("x", "0"), 2), i
    if base_ch == "o":
        return int(digits, 8), i
    return int(digits, 16), i


def _parse_verilog_sized(s: str, i: int) -> tuple[int, int]:
    """如 8'hFF"""
    n = len(s)
    j = i
    while j < n and s[j].isdigit():
        j += 1
    if j >= n or s[j] != "'":
        return 0, i
    return _parse_verilog_unsized(s, j)


_VER_WS = re.compile(r"\s+")


def parse_ralf(
    text: str,
    *,
    path: Path | None = None,
    line_origins: Sequence[tuple[Path, int]] | None = None,
) -> RalfDocument:
    """将 RALF 源文本解析为 `RalfDocument`。"""
    p = _Parser(text, path=path, line_origins=line_origins)
    doc = p.parse_document()
    return doc


def normalize_ralf_whitespace(text: str) -> str:
    """去掉注释与多余空白，用于测试比对（不保证与工具链字节级一致）。"""
    p = _Parser(text)
    p.skip_ws_and_comments()
    out: list[str] = []
    while p._i < p._n:
        c = p._s[p._i]
        if c in " \t\r\n":
            if out and out[-1] != " ":
                out.append(" ")
            p._advance()
        elif c == "/" and p._peek(1) == "/":
            while p._i < p._n and p._s[p._i] != "\n":
                p._advance()
        elif c == "/" and p._peek(1) == "*":
            p._advance(2)
            while p._i + 1 < p._n and not (
                p._s[p._i] == "*" and p._s[p._i + 1] == "/"
            ):
                p._advance()
            p._advance(min(2, p._n - p._i))
        else:
            out.append(c)
            p._advance()
    s = "".join(out).strip()
    return _VER_WS.sub(" ", s)
