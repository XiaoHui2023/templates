"""Check project SV declaration policy on generated sources, not vendor libraries."""

import argparse
from pathlib import Path
import re


TOKEN = re.compile(
    r'(?P<ignored>//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\\\S+)'
    r'|(?P<value>\d+(?:\.\d+)?(?:fs|ps|ns|us|ms|s)\b|[a-zA-Z_$][\w$]*|\S)'
)
TIME = re.compile(r"\d+(?:\.\d+)?(?:fs|ps|ns|us|ms|s)")


def check_timing_package(tokens, fail):
    """Allow time declarations and subroutines that use time."""
    cursor = 0
    scales = set()
    timed = False
    while cursor < len(tokens):
        keyword = tokens[cursor]
        if keyword in {"timeunit", "timeprecision"}:
            finish = tokens.index(";", cursor)
            scales.add(keyword)
            if keyword == "timeunit" and "/" in tokens[cursor:finish]:
                scales.add("timeprecision")
        elif keyword in {"function", "task"}:
            finish = tokens.index("end" + keyword, cursor)
            body = tokens[cursor:finish]
            if not any(TIME.fullmatch(t) or t in {"$time", "$realtime"} for t in body):
                fail(f"non-timing {keyword} is forbidden inside a package")
            timed = True
            if tokens[finish + 1:finish + 2] == [":"]:
                finish += 2
        else:
            fail(f"package may only contain time declarations and timing subroutines, not {keyword}")
        cursor = finish + 1
    if scales != {"timeunit", "timeprecision"} or not timed:
        fail("package requires an explicit timeunit, timeprecision and timed procedure")


def check_source(source, name):
    """Reject typedef outside a class and misplaced package declarations."""
    matches = [m for m in TOKEN.finditer(source) if m.lastgroup == "value"]
    tokens = [m.group() for m in matches]
    depth = 0
    index = 0
    while index < len(tokens):
        token = tokens[index]

        def fail(reason):
            line = source.count("\n", 0, matches[index].start()) + 1
            raise ValueError(f"{name}:{line}: {reason}")

        if token == "typedef" and not depth:
            fail("typedef must be declared inside its owning class")
        if token == "class" and (index == 0 or tokens[index - 1] != "typedef"):
            depth += 1
        elif token == "endclass":
            depth -= 1
        elif token == "package":
            start = tokens.index(";", index) + 1
            end = tokens.index("endpackage", start)
            body = tokens[start:end]
            if "typedef" in body:
                fail("typedef is forbidden inside a package")
            check_timing_package(body, fail)
            index = end
        index += 1


def self_test():
    check_source('class base_item; typedef enum {STATE} state_t; endclass', "class-positive")
    check_source('package timer; timeunit 1ns/1ps; task automatic wait_ns(input int count); '
                 '#(count * 1ns); endtask endpackage', "timed-positive")
    for source in (
        'typedef int state_t;',
        'typedef class item; class item; endclass',
        'package timer; timeunit 1ns/1ps; typedef int state_t; '
        'task automatic wait_ns; #1ns; endtask endpackage',
        'package utility; timeunit 1ns/1ps; int x; task automatic wait_ns; #1ns; endtask endpackage',
        'package utility; timeunit 1ns/1ps; function int get(); return 1; endfunction endpackage',
        'package utility; timeunit 1ns/1ps; function int get(); return 1; endfunction '
        'task automatic wait_ns; #1ns; endtask endpackage',
    ):
        try:
            check_source(source, "negative-control")
        except ValueError:
            continue
        raise AssertionError(f"policy accepted: {source}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("sources", nargs="*", type=Path)
    args = parser.parse_args()
    if not args.self_test and not args.sources:
        parser.error("provide a generated SV file or --self-test")
    if args.self_test:
        self_test()
    for path in args.sources:
        check_source(path.read_text(encoding="utf-8-sig"), path)
