from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


DECL_RE = re.compile(r"\b(?:extern\s+)?(?:task|function)\b[^;]*?\((.*?)\)", re.S)
DIRS = ("input ", "output ", "inout ", "ref ", "const ref ")
NON_INPUT_DIRS = ("output ", "inout ", "ref ", "const ref ")


def split_params(params: str) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    depth = 0
    for ch in params:
        if ch in "([{":
            depth += 1
        elif ch in ")]}" and depth:
            depth -= 1
        if ch == "," and depth == 0:
            item = "".join(cur).strip()
            if item:
                out.append(item)
            cur = []
        else:
            cur.append(ch)
    item = "".join(cur).strip()
    if item:
        out.append(item)
    return out


def check_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    for match in DECL_RE.finditer(text):
        params = " ".join(match.group(1).split())
        if not any(direction in params for direction in NON_INPUT_DIRS):
            continue
        bad = [
            param
            for param in split_params(params)
            if not param.startswith(DIRS)
        ]
        if bad:
            line = text[: match.start()].count("\n") + 1
            errors.append(f"{path}:{line}: parameters must all have explicit directions: {bad}")
    return errors


def iter_sv_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(
                p
                for p in path.rglob("*")
                if p.suffix in {".sv", ".j2"}
                and not any(part.startswith(".") for part in p.parts)
            )
        elif path.suffix in {".sv", ".j2"}:
            files.append(path)
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    for path in iter_sv_files(args.paths):
        errors.extend(check_file(path))

    if errors:
        print("\n".join(errors))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
