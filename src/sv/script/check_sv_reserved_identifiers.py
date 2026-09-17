from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


SV_KEYWORDS = frozenset(
    """
    accept_on alias always always_comb always_ff always_latch and assert assign assume automatic
    before begin bind bins binsof bit break buf bufif0 bufif1 byte case casex casez cell chandle
    checker class clocking cmos config const constraint context continue cover covergroup coverpoint
    cross deassign default defparam design disable dist do edge else end endcase endchecker endclass
    endclocking endconfig endfunction endgenerate endgroup endinterface endmodule endpackage
    endprimitive endprogram endproperty endsequence endspecify endtable endtask enum event eventually
    expect export extends extern final first_match for force foreach forever fork forkjoin function
    generate genvar global highz0 highz1 if iff ifnone ignore_bins illegal_bins implements implies
    import incdir include initial inout input inside int integer interconnect intersect join join_any
    join_none large let liblist library local localparam logic longint macromodule matches medium
    modport module nand negedge nettype new nexttime nmos nor noshowcancelled not notif0 notif1 null or
    output package packed parameter pmos posedge primitive priority program property protected pull0
    pull1 pulldown pullup pulsestyle_ondetect pulsestyle_onevent pure rand randc randcase randsequence
    rcmos real realtime ref reg reject_on release repeat restrict return rnmos rpmos rtran rtranif0
    rtranif1 s_always s_eventually s_nexttime s_until s_until_with scalared sequence shortint
    shortreal showcancelled signed small soft solve specify specparam static string strong strong0
    strong1 struct super supply0 supply1 sync_accept_on sync_reject_on table tagged task this throughout
    time timeprecision timeunit tran tranif0 tranif1 tri tri0 tri1 triand trior trireg type typedef
    union unique unique0 unsigned until until_with untyped use uwire var vectored virtual void wait
    wait_order wand weak weak0 weak1 while wildcard wire with within wor xnor xor
    """.split()
)
TYPE_KEYWORDS = frozenset(
    "bit byte chandle event int integer logic longint real realtime reg shortint shortreal string time "
    "tri tri0 tri1 triand trior trireg uwire void wand wire wor".split()
)
TYPE_QUALIFIERS = frozenset("packed scalared signed unsigned vectored".split())
NAMED_DECLARATIONS = frozenset("checker class config interface module package primitive program".split())
NAME_DELIMITERS = frozenset({"(", ",", ";", "=", ")", "[", "]"})


@dataclass(frozen=True)
class Token:
    """Stores one significant SystemVerilog token and its source line."""

    text: str
    line: int
    is_identifier: bool


def tokenize(text: str) -> list[Token]:
    """Tokenizes identifiers and punctuation while omitting comments and literals.

    Args:
        text: SystemVerilog source text.

    Returns:
        Significant tokens with line locations.
    """
    tokens: list[Token] = []
    index = 0
    line = 1
    while index < len(text):
        char = text[index]
        if char == "\n":
            line += 1
            index += 1
            continue
        if char.isspace():
            index += 1
            continue
        if text.startswith("//", index):
            end = text.find("\n", index + 2)
            index = len(text) if end < 0 else end
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                end = len(text) - 2
            line += text[index : end + 2].count("\n")
            index = end + 2
            continue
        if char == '"':
            index += 1
            while index < len(text):
                if text[index] == "\\":
                    index += 2
                    continue
                if text[index] == '"':
                    index += 1
                    break
                if text[index] == "\n":
                    line += 1
                index += 1
            continue
        if char == "\\":
            end = index + 1
            while end < len(text) and not text[end].isspace():
                end += 1
            tokens.append(Token(text[index:end], line, True))
            index = end
            continue
        if char.isalpha() or char == "_":
            end = index + 1
            while end < len(text) and (text[end].isalnum() or text[end] in "_$"):
                end += 1
            tokens.append(Token(text[index:end], line, True))
            index = end
            continue
        tokens.append(Token(char, line, False))
        index += 1
    return tokens


def check_source(text: str, source: str) -> list[str]:
    """Finds reserved keywords used in common identifier positions.

    Args:
        text: SystemVerilog source text.
        source: Diagnostic source label.

    Returns:
        Diagnostics for invalid identifier uses.
    """
    tokens = tokenize(text)
    errors: list[str] = []
    for index, token in enumerate(tokens):
        if token.text not in SV_KEYWORDS:
            continue
        previous = tokens[index - 1] if index > 0 else None
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        used_as_name = False
        if token.text == "new" and previous is not None:
            before_previous = tokens[index - 2] if index > 1 else None
            if previous.text == "function" or (
                previous.text == "."
                and before_previous is not None
                and before_previous.text == "super"
            ):
                continue
        if previous is not None and previous.text == "task" and token.text != "automatic":
            used_as_name = True
        elif (
            previous is not None
            and previous.text == "function"
            and following is not None
            and following.text == "("
        ):
            used_as_name = True
        elif previous is not None and previous.text in {".", "::"}:
            used_as_name = True
        elif previous is not None and previous.text == ":":
            before_colon = tokens[index - 2] if index > 1 else None
            used_as_name = before_colon is not None and before_colon.text in {
                ":",
                "begin",
                "fork",
                "generate",
            }
        elif previous is not None and following is not None and following.text in NAME_DELIMITERS:
            if token.text not in TYPE_QUALIFIERS:
                used_as_name = (
                    previous.text in TYPE_KEYWORDS
                    or previous.text == "]"
                    or (previous.is_identifier and previous.text not in SV_KEYWORDS)
                )
        elif previous is not None and previous.text in NAMED_DECLARATIONS:
            used_as_name = True
        if used_as_name:
            errors.append(f"{source}:{token.line}: reserved keyword used as identifier: {token.text}")
    return errors


def check_file(path: Path) -> list[str]:
    """Checks one generated SystemVerilog source file.

    Args:
        path: Generated SystemVerilog source file.

    Returns:
        Diagnostics for invalid identifier uses.
    """
    return check_source(path.read_text(encoding="utf-8"), str(path))


def iter_sv_files(paths: list[Path]) -> list[Path]:
    """Expands source files and directories into a stable file list.

    Args:
        paths: Files or directories to scan.

    Returns:
        Sorted unique SystemVerilog files.
    """
    files: set[Path] = set()
    for path in paths:
        if path.is_dir():
            files.update(path.rglob("*.sv"))
        elif path.suffix == ".sv":
            files.add(path)
    return sorted(files)


def main() -> int:
    """Runs the reserved identifier scan from command-line paths.

    Returns:
        Process status code.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    for path in iter_sv_files(args.paths):
        errors.extend(check_file(path))
    if errors:
        print("\n".join(errors))
        return 1
    print("SystemVerilog reserved identifier scan ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
