#!/usr/bin/env python3
"""Estimate the cohesion of a module by approximating LCOM.

Cohesion is the degree to which the parts of a module belong together. This
script turns that question into two structural numbers you can act on:

  * CK LCOM (Chidamber & Kemerer, version 1): |P| - |Q| (floored at 0), where
    P counts pairs of nodes that share NO common element and Q counts pairs
    that DO. A high value means the parts mostly don't touch the same data --
    a lack of cohesion. 0 means well connected.

  * Clusters (connected components): how many independent groups the nodes
    fall into.
    This is the actionable number -- it is the count of modules this one could
    cleanly split into. 1 = cohesive; 2+ = a grab-bag.

Cohesion is NOT an object-oriented idea. So each language is analyzed in two
ways, and whichever applies is reported:

  * OO mode      -- a class/object is the module. Nodes are methods, two
                    methods are linked when they touch a shared field. This is
                    the classic LCOM from the literature.

  * file mode    -- a file/script is the module. Nodes are top-level
                    functions, two functions are linked when they reference a
                    shared module-level symbol OR one calls the other. This is
                    the dominant case for R and Bash, and applies to any file
                    of free functions.

Backends:
  * Python -- precise: a real `ast` parse (classes via self.<attr>; module
              functions via module globals + call graph).
  * R      -- heuristic regex: top-level `name <- function(...)` plus
              R6Class / setRefClass objects (self$x / private$x fields).
  * Bash   -- heuristic regex: `name() { ... }` / `function name` plus
              referenced global variables and the call graph.

The numbers are diagnostic signals, not verdicts. The R and Bash backends are
heuristic and can miss dynamic constructs; treat their output as a prompt to
look closer, never as proof. See ../references/cohesion-taxonomy.md for what
LCOM can and cannot tell you ("why is more important than how").

Usage:
    python lcom.py <path...> [--lang auto|python|r|bash] [--json]
        [--top N] [--output FILE]

Stdlib only; runs on any Python 3.8+.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path


@dataclass
class ModuleReport:
    """Cohesion numbers for one analyzed module (a class or a file).

    kind is "class" or "file"; node_label is "method" or "function";
    edge_label is "field" or "shared symbol". touches maps each node to the
    set of elements it touches (fields, or shared symbols plus callee tokens).
    """

    name: str
    kind: str
    node_label: str
    edge_label: str
    nodes: list[str]
    touches: dict[str, set[str]]

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def lcom(self) -> int:
        """CK LCOM v1: |P| - |Q|, floored at 0."""
        p = q = 0
        for a, b in combinations(self.nodes, 2):
            if self.touches[a] & self.touches[b]:
                q += 1
            else:
                p += 1
        return max(p - q, 0)

    @property
    def clusters(self) -> int:
        """Number of clusters (connected components) in the node/element graph."""
        if not self.nodes:
            return 0
        parent = {n: n for n in self.nodes}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: str, y: str) -> None:
            parent[find(x)] = find(y)

        for a, b in combinations(self.nodes, 2):
            if self.touches[a] & self.touches[b]:
                union(a, b)
        return len({find(n) for n in self.nodes})

    def interpretation(self) -> str:
        if self.node_count < 2:
            return "only one " + self.node_label + " -- cohesion is trivially fine"
        comp = self.clusters
        if comp <= 1:
            return "well connected (1 cluster) -- cohesive"
        plural = "classes" if self.kind == "class" else "files"
        return (
            f"{comp} disjoint clusters -- this {self.kind} could split into "
            f"{comp} {plural}; inspect whether the clusters truly belong apart"
        )


def analyze_python(path: Path, source: str) -> list[ModuleReport]:
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        sys.stderr.write(f"warning: skipping {path}: {exc}\n")
        return []

    reports = [
        r
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        for r in [_python_class(node)]
        if r
    ]

    file_report = _python_file(path, tree)
    if file_report:
        reports.append(file_report)
    return reports


_PY_EXCLUDED_METHODS = {"__init__", "__new__"}


def _python_class(node: ast.ClassDef) -> ModuleReport | None:
    """Collect self.<attr> touches per method, excluding constructors.

    Constructors conventionally touch every field, which bridges otherwise
    unrelated method clusters and masks a real lack of cohesion, so they are
    left out like standard LCOM tooling does.
    """
    methods: dict[str, set[str]] = {}
    for item in node.body:
        if (
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name not in _PY_EXCLUDED_METHODS
        ):
            methods[item.name] = _self_attrs(item)
    if len(methods) < 2:
        return None
    return ModuleReport(
        name=node.name,
        kind="class",
        node_label="method",
        edge_label="field",
        nodes=list(methods),
        touches=methods,
    )


def _self_attrs(func: ast.AST) -> set[str]:
    """Collect `self.<attr>` names accessed within a method body."""
    attrs: set[str] = set()
    for sub in ast.walk(func):
        if (
            isinstance(sub, ast.Attribute)
            and isinstance(sub.value, ast.Name)
            and sub.value.id == "self"
        ):
            attrs.add(sub.attr)
    return attrs


def _python_file(path: Path, tree: ast.Module) -> ModuleReport | None:
    """Treat module-level functions as nodes linked by shared globals and calls.

    Each function owns an identity token so a caller that references a sibling
    connects to the callee holding that same token.
    """
    funcs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(funcs) < 2:
        return None

    func_names = {f.name for f in funcs}
    module_globals = _module_globals(tree)

    touches: dict[str, set[str]] = {}
    for f in funcs:
        used: set[str] = {"f:" + f.name}
        for sub in ast.walk(f):
            if isinstance(sub, ast.Name):
                if sub.id in module_globals:
                    used.add("g:" + sub.id)
                if sub.id in func_names and sub.id != f.name:
                    used.add("f:" + sub.id)
        touches[f.name] = used

    return ModuleReport(
        name=path.name,
        kind="file",
        node_label="function",
        edge_label="shared symbol",
        nodes=[f.name for f in funcs],
        touches=touches,
    )


def _module_globals(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


@dataclass
class _FuncDef:
    name: str
    body: str
    refs: set[str] = field(default_factory=set)


def _strip_comments(source: str, marker: str = "#") -> str:
    """Drop end-of-line comments. Naive but good enough for symbol scanning."""
    out = []
    for line in source.splitlines():
        idx = line.find(marker)
        out.append(line if idx == -1 else line[:idx])
    return "\n".join(out)


def _slice_body(source: str, open_idx: int) -> str:
    """Return the brace-balanced body starting at the `{` at open_idx."""
    depth = 0
    for i in range(open_idx, len(source)):
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[open_idx + 1 : i]
    return source[open_idx + 1 :]


def _build_file_report(
    path: Path, defs: list[_FuncDef], top_symbols: set[str]
) -> ModuleReport | None:
    """Link functions by shared module symbols and calls via identity tokens."""
    if len(defs) < 2:
        return None
    func_names = {d.name for d in defs}
    touches: dict[str, set[str]] = {}
    for d in defs:
        used: set[str] = {"f:" + d.name}
        for ref in d.refs:
            if ref in top_symbols:
                used.add("g:" + ref)
            if ref in func_names and ref != d.name:
                used.add("f:" + ref)
        touches[d.name] = used
    return ModuleReport(
        name=path.name,
        kind="file",
        node_label="function",
        edge_label="shared symbol",
        nodes=[d.name for d in defs],
        touches=touches,
    )


_R_FUNC = re.compile(r"(?P<name>[A-Za-z.][\w.]*)\s*(?:<-|=)\s*function\s*\(", re.MULTILINE)
_R_TOP_ASSIGN = re.compile(r"^(?P<name>[A-Za-z.][\w.]*)\s*(?:<-|=)\s*(?!function\b)", re.MULTILINE)
_R_TOKEN = re.compile(r"[A-Za-z.][\w.]*")
_R6_FIELD = re.compile(r"(?:self|private)\$([A-Za-z.][\w.]*)")


def analyze_r(path: Path, source: str) -> list[ModuleReport]:
    """Report OO classes plus top-level functions, skipping class internals.

    Methods defined inside an R6Class / setRefClass block are covered by OO
    mode already, so file mode only sees functions outside those spans.
    """
    src = _strip_comments(source, "#")
    reports: list[ModuleReport] = []

    oo_spans: list[tuple[int, int]] = []
    reports.extend(_r_oo_report(src, oo_spans))

    defs: list[_FuncDef] = []
    for m in _R_FUNC.finditer(src):
        if any(start <= m.start() < end for start, end in oo_spans):
            continue
        open_paren = src.index("(", m.end() - 1)
        body = _r_function_body(src, open_paren)
        defs.append(_FuncDef(m.group("name"), body, set(_R_TOKEN.findall(body))))

    top_symbols = {m.group("name") for m in _R_TOP_ASSIGN.finditer(src)}
    file_report = _build_file_report(path, defs, top_symbols)
    if file_report:
        reports.append(file_report)
    return reports


def _r_function_body(source: str, open_paren_idx: int) -> str:
    """Grab a heuristic body for an R function: prefer a `{ }` block."""
    brace = source.find("{", open_paren_idx)
    nl = source.find("\n", open_paren_idx)
    if brace != -1 and (nl == -1 or brace < nl + 200):
        return _slice_body(source, brace)
    end = source.find("\n", open_paren_idx)
    return source[open_paren_idx : end if end != -1 else len(source)]


def _r_oo_report(src: str, oo_spans: list[tuple[int, int]]) -> list[ModuleReport]:
    """Detect R6Class / setRefClass objects and treat methods+fields as a class.

    Records each object's character span in `oo_spans` so file mode can skip
    the methods defined inside it.
    """
    reports: list[ModuleReport] = []
    for kw in ("R6Class", "setRefClass"):
        for m in re.finditer(re.escape(kw) + r"\s*\(", src):
            open_paren = src.index("(", m.end() - 1)
            block = _slice_body_parens(src, open_paren)
            oo_spans.append((open_paren, open_paren + len(block)))
            methods = {
                fm.group("name"): set(
                    _R6_FIELD.findall(_r_function_body(block, block.index("(", fm.end() - 1)))
                )
                for fm in _R_FUNC.finditer(block)
            }
            class_name = _r_class_name(block) or kw
            if len(methods) >= 2:
                reports.append(
                    ModuleReport(
                        name=class_name,
                        kind="class",
                        node_label="method",
                        edge_label="field",
                        nodes=list(methods),
                        touches=methods,
                    )
                )
    return reports


def _r_class_name(block: str) -> str | None:
    """The class name R6Class/setRefClass is given as its first string arg."""
    m = re.match(r"\s*[\"']([^\"']+)[\"']", block)
    return m.group(1) if m else None


def _slice_body_parens(source: str, open_idx: int) -> str:
    depth = 0
    for i in range(open_idx, len(source)):
        if source[i] == "(":
            depth += 1
        elif source[i] == ")":
            depth -= 1
            if depth == 0:
                return source[open_idx + 1 : i]
    return source[open_idx + 1 :]


_BASH_FUNC = re.compile(
    r"(?:^|\n)\s*(?:function\s+)?(?P<name>[A-Za-z_][\w-]*)\s*\(\s*\)\s*\{",
    re.MULTILINE,
)
_BASH_VARREF = re.compile(r"\$\{?(?P<name>[A-Za-z_]\w*)")
_BASH_ASSIGN = re.compile(r"(?:^|\n)\s*(?:export\s+)?(?P<name>[A-Za-z_]\w*)=", re.MULTILINE)
_BASH_WORD = re.compile(r"[A-Za-z_][\w-]*")


def analyze_bash(path: Path, source: str) -> list[ModuleReport]:
    """Report top-level functions linked by globals and calls.

    Bare command words count as callee links; only assignments outside any
    function body count as module-level symbols.
    """
    src = _strip_comments(source, "#")
    defs: list[_FuncDef] = []
    for m in _BASH_FUNC.finditer(src):
        brace = src.index("{", m.end() - 1)
        body = _slice_body(src, brace)
        refs = {vm.group("name") for vm in _BASH_VARREF.finditer(body)}
        refs |= set(_BASH_WORD.findall(body))
        defs.append(_FuncDef(m.group("name"), body, refs))

    top_symbols = {m.group("name") for m in _BASH_ASSIGN.finditer(src)}
    top_symbols = {s for s in top_symbols if _assigned_at_top(src, s)}
    report = _build_file_report(path, defs, top_symbols)
    return [report] if report else []


def _assigned_at_top(src: str, name: str) -> bool:
    """True if `name=` appears at indentation level outside a brace block."""
    depth = 0
    for line in src.splitlines():
        stripped = line.strip()
        if depth == 0 and re.match(rf"(?:export\s+)?{re.escape(name)}=", stripped):
            return True
        depth += line.count("{") - line.count("}")
    return False


_BACKENDS = {"python": analyze_python, "r": analyze_r, "bash": analyze_bash}
_EXT_LANG = {
    ".py": "python",
    ".r": "r",
    ".R": "r",
    ".sh": "bash",
    ".bash": "bash",
}


def detect_lang(path: Path) -> str | None:
    return _EXT_LANG.get(path.suffix)


def analyze_path(path: Path, lang: str) -> list[ModuleReport]:
    source = path.read_text(encoding="utf-8", errors="replace")
    return _BACKENDS[lang](path, source)


def iter_source_files(path: Path, lang: str | None) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    targets = sorted(path.rglob("*")) if path.is_dir() else [path]
    for f in targets:
        if not f.is_file():
            continue
        resolved = lang or detect_lang(f)
        if resolved in _BACKENDS:
            files.append((f, resolved))
    return files


def render_text(items: list[tuple[Path, ModuleReport]], hidden: int, total: int, multi: int) -> str:
    """Render the worst-first shortlist with a truncation note and a summary line."""
    lines = []
    for path, report in items:
        lines.append(f"# {path}")
        lines.append(
            f"  {report.kind} {report.name}: {report.node_count} {report.node_label}s, "
            f"LCOM={report.lcom}, clusters={report.clusters}"
        )
        lines.append(f"      -> {report.interpretation()}")
    if hidden:
        lines.append(f"... {hidden} more (raise --top)")
    lines.append(f"{total} modules, {multi} with 2+ clusters")
    return "\n".join(lines)


def report_to_dict(path: Path, r: ModuleReport) -> dict:
    return {
        "file": str(path),
        "module": r.name,
        "kind": r.kind,
        "nodes": r.node_count,
        "lcom": r.lcom,
        "clusters": r.clusters,
        "interpretation": r.interpretation(),
    }


def emit(payload: str, output: Path | None) -> int:
    """Write payload to output, or print it; 3 when the output is unwritable."""
    if output is None:
        print(payload)
        return 0
    try:
        output.write_text(payload + "\n", encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"error: cannot write {output}: {exc}\n")
        return 3
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse flags, analyze every path, and print or store the worst-first report."""
    parser = argparse.ArgumentParser(
        description="Estimate module cohesion via LCOM (CK v1) and clusters. "
        "Python is precise (ast); R and Bash are heuristic.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n"
        "  lcom.py src/\n"
        "  lcom.py mod.py --top 5 --json\n"
        "exit: 0 ok | 1 input not found | 2 usage | 3 bad input or no result",
    )
    parser.add_argument("paths", nargs="+", type=Path, help="files or directories")
    parser.add_argument(
        "--lang",
        choices=["auto", "python", "r", "bash"],
        default="auto",
        help="force a language (default: auto)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--top", type=int, default=20, help="worst modules shown (default: 20)")
    parser.add_argument(
        "--output", metavar="FILE", type=Path, help="write the report here, not stdout"
    )
    args = parser.parse_args(argv)

    for p in args.paths:
        if not p.exists():
            sys.stderr.write(f"error: no such path: {p}\n")
            return 1

    lang = None if args.lang == "auto" else args.lang
    collected: list[tuple[Path, list[ModuleReport]]] = []
    for p in args.paths:
        for f, resolved in iter_source_files(p, lang):
            collected.append((f, analyze_path(f, resolved)))

    if not collected:
        sys.stderr.write("No analyzable source files found.\n")
        if args.json:
            emit("[]", args.output)
        return 3

    items = [(f, r) for f, reports in collected for r in reports]
    items.sort(key=lambda item: (-item[1].clusters, -item[1].lcom, str(item[0]), item[1].name))
    shown = items[: max(args.top, 0)]
    total = len(items)
    multi = sum(1 for _, r in items if r.clusters >= 2)

    if args.json:
        payload = json.dumps([report_to_dict(f, r) for f, r in shown], indent=2)
    else:
        payload = render_text(shown, total - len(shown), total, multi)
    return emit(payload, args.output)


if __name__ == "__main__":
    sys.exit(main())
