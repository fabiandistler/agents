#!/usr/bin/env python3
"""Reject line-number citations of repository files in the factory docs.

Run from repo root:
    python3 scripts/check_line_cites.py    # exit 1 when a line citation remains

docs/factory/ and docs/agents/ describe code that keeps changing. A citation
such as `implementer_claim.py:68` is updated by hand, drifts with any edit to
the cited file, and nothing notices (issue #957). This gate reads every
Markdown file under those two directories and checks each code span:

- line citations: a `<path>:<N>`, `<path>:<N>-<M>` or `<path>:<N>,<M>` whose
  path is a tracked file (`scripts/pr_risk.py`) or a tracked file's basename
  (`pr_risk.py`) fails. Cite the symbol instead: `module.symbol` for a Python
  module under scripts/, and the file name plus a job id, step name or heading
  for any other file. A span whose text before the colon names no tracked file
  (a time such as `12:30`, a URL with a port) is not a citation.
- symbol citations: a `module.symbol` whose module is a tracked
  scripts/<module>.py must name a `def`, `class` or top-level assignment of
  that module. A span that is a file name (`pr_risk.py`,
  `agent_run_settings.json`) is not a symbol citation.

docs/adr/ and docs/wiki/ are dated records and stay out of scope.
Stdlib-only, matching the other scripts/check_*.py gates.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parent.parent

CHECKED_DIRS = ("docs/factory", "docs/agents")

USAGE = """usage: check_line_cites.py [--root DIR] [--help]

Flag `<file>:<N>` line citations of tracked files, and `module.symbol`
citations of scripts/ modules that lack the symbol, in the Markdown files
under docs/factory/ and docs/agents/.

  --root DIR  git checkout to scan (default: this script's repo)
  --help      show this message

examples:
  python3 scripts/check_line_cites.py
  python3 scripts/check_line_cites.py --root /path/to/checkout

exit: 0 no line citations | 1 citations found | 2 usage error
"""

DIRECTION = (
    "cite the symbol instead of the line: `module.symbol` for a Python module under "
    "scripts/ (a def, class or top-level assignment), otherwise the file name plus a "
    "job id, step name or heading"
)

CODE_SPAN = re.compile(r"`([^`\n]+)`")
# A path-like token, a colon, then line numbers joined by `-` or `,`. Not
# preceded or followed by a path character, so `a.py:12x` is not a citation.
LINE_CITATION = re.compile(r"(?<![\w./-])(?P<path>[\w./-]+):(?P<lines>\d+(?:[-,]\d+)*)(?![\w.:/-])")
SYMBOL_CITATION = re.compile(r"(?P<module>[a-z_][a-z0-9_]*)\.(?P<symbol>[A-Za-z_]\w*)")


def tracked_files(root: Path) -> list[str]:
    """Repo-relative paths `git ls-files` lists for `root`."""
    listing = subprocess.run(
        ["git", "ls-files", "-z"],  # noqa: S607 -- Git intentionally resolves from PATH.
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [path for path in listing.stdout.split("\0") if path]


def checked_docs(tracked: list[str]) -> list[str]:
    return sorted(
        path
        for path in tracked
        if path.endswith(".md") and any(path.startswith(f"{d}/") for d in CHECKED_DIRS)
    )


def module_names(source: str) -> set[str]:
    """Names a module defines at top level: def, class and assignment targets."""
    names: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                names.update(child.id for child in ast.walk(target) if isinstance(child, ast.Name))
    return names


class Citations:
    """What a doc may cite, read once from the checkout."""

    def __init__(self, root: Path, tracked: list[str]) -> None:
        self.root = root
        self.paths = set(tracked)
        self.basenames = {PurePosixPath(path).name for path in tracked}
        self.modules = {
            PurePosixPath(path).stem
            for path in tracked
            if PurePosixPath(path).parent == PurePosixPath("scripts") and path.endswith(".py")
        }
        self._names: dict[str, set[str]] = {}

    def is_file(self, mention: str) -> bool:
        mention = mention.removeprefix("./")
        return mention in self.paths or mention in self.basenames

    def defines(self, module: str, symbol: str) -> bool:
        if module not in self._names:
            source = (self.root / "scripts" / f"{module}.py").read_text(encoding="utf-8")
            self._names[module] = module_names(source)
        return symbol in self._names[module]


def violations_in(doc: str, citations: Citations) -> list[tuple[int, str]]:
    """(line number, message) for each line or dead symbol citation in `doc`."""
    found: list[tuple[int, str]] = []
    text = (citations.root / doc).read_text(encoding="utf-8")
    for number, line in enumerate(text.splitlines(), start=1):
        for span in CODE_SPAN.findall(line):
            for match in LINE_CITATION.finditer(span):
                if citations.is_file(match.group("path")):
                    found.append((number, f"line citation `{match.group(0)}`"))
            symbol = SYMBOL_CITATION.fullmatch(span.strip())
            if (
                symbol
                and symbol.group("module") in citations.modules
                and not citations.is_file(symbol.group(0))
                and not citations.defines(symbol.group("module"), symbol.group("symbol"))
            ):
                module_path = f"scripts/{symbol.group('module')}.py"
                message = f"`{symbol.group(0)}` names no def, class or top-level assignment"
                message += f" in {module_path}"
                found.append((number, message))
    return found


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--help" in args or "-h" in args:
        sys.stdout.write(USAGE)
        return 0
    root = REPO_ROOT
    if args[:1] == ["--root"] and len(args) == 2:
        root = Path(args[1]).resolve()
    elif args:
        sys.stderr.write(f"unknown argument: {' '.join(args)}\n{USAGE}")
        return 2
    tracked = tracked_files(root)
    citations = Citations(root, tracked)
    docs = checked_docs(tracked)
    violations = [
        f"{doc}:{number}: {message}"
        for doc in docs
        for number, message in violations_in(doc, citations)
    ]
    if violations:
        sys.stderr.write(f"line citations: {len(violations)} in {len(docs)} docs\n")
        for violation in violations:
            sys.stderr.write(f"  - {violation}\n")
        sys.stderr.write(f"\nFix: {DIRECTION}.\n")
        return 1
    print(f"line citations ok ({len(docs)} docs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
