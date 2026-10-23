#!/usr/bin/env python3
"""Check the self-contained POC toolchain copy of the Python baseline."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL = REPO_ROOT / "instructions" / "30-python.md"
SKILL_COPY = REPO_ROOT / "skills" / "poc-spec-loop" / "references" / "toolchains.md"
START = "<!-- python-project-baseline:start -->"
END = "<!-- python-project-baseline:end -->"

USAGE = """usage: check_python_baseline.py [--help]

Check that the self-contained Python baseline in toolchains.md matches instructions/30-python.md.

  --help  show this message

exit: 0 copies match | 1 baseline drift or marker error | 2 usage error | 3 file read error
examples:
  python3 scripts/check_python_baseline.py
  python3 scripts/check_python_baseline.py --help
"""


def baseline_block(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError(f"{path.relative_to(REPO_ROOT)} must have one start and end marker")
    start = text.index(START) + len(START)
    end = text.index(END, start)
    if end < start:
        raise ValueError(f"{path.relative_to(REPO_ROOT)} has reversed baseline markers")
    return text[start:end].strip()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["--help"] or args == ["-h"]:
        sys.stdout.write(USAGE)
        return 0
    if args:
        sys.stderr.write(f"unknown argument: {' '.join(args)}\n{USAGE}")
        return 2

    try:
        canonical = baseline_block(CANONICAL)
        copied = baseline_block(SKILL_COPY)
    except OSError as exc:
        sys.stderr.write(f"cannot read Python baseline source: {exc.filename}\n")
        return 3
    except ValueError as exc:
        sys.stderr.write(f"Python baseline markers invalid: {exc}\n")
        return 1

    if canonical != copied:
        sys.stderr.write(
            "Python baseline drift: update the `toolchains.md` copy to match `instructions/30-python.md`\n"
        )
        return 1
    print("Python baseline copies match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
