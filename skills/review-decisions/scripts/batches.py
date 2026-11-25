#!/usr/bin/env python3
"""Split a diff too large for one classifier context into batches by file, and merge the answers.

usage: batches.py split DIFF --out DIR | batches.py merge DIR

  split DIFF --out DIR  Cut a `git diff` into one chunk per file, pack the chunks
                        in diff order into batches of at most 200000 bytes,
                        write DIR/batch-<k>.diff and DIR/batches.json, and print
                        that JSON: {"max_bytes", "batches": [{"batch", "file",
                        "paths", "bytes", "oversize"}]}. Every file lands in
                        exactly one batch; a file over the limit gets a batch of
                        its own with "oversize": true.
  merge DIR             Read the classifier's answer per batch from
                        DIR/batch-<k>.answer.md and print one queue as JSON:
                        {"boundaries", "deviation", "cards", "unclassified"}.
                        Cards keep the category order; each carries "batch" and
                        "unchecked_across_batches". The files of a batch without
                        a readable answer are listed in "unclassified" with a
                        reason: the line in DIR/batch-<k>.failed, or the size.

exit codes: 0 ok; 1 usage error; 2 DIFF or DIR/batches.json missing;
3 DIFF is not a git diff.

examples:
  python3 scripts/batches.py split /tmp/rd/diff.patch --out /tmp/rd/batches
  python3 scripts/batches.py merge /tmp/rd/batches
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import cli
from cli import ScriptError

MAX_BYTES = 200_000
FILE_HEADER = "diff --git "
HEADER_PATHS = re.compile(r"^diff --git a/(.*) b/(.*)$")

# Cost-of-reversal order, the classifier's categories.
CATEGORIES = ["deviation", "public surface", "schema and data", "behaviour", "tests"]
# Decisions whose other half may sit in another batch: a deviation judged on part
# of the diff, and a surface or format that code elsewhere relies on.
SPAN_CATEGORIES = {"deviation", "public surface", "schema and data"}
WEAKENED_TEST = "deleted or weakened test"
FIELDS = {
    "Category": "category",
    "Location": "location",
    "Criterion": "criterion",
    "Chosen": "chosen",
    "Alternatives": "alternatives",
    "Cost to undo": "cost_to_undo",
    "Lean": "lean",
    "Depends on": "depends_on",
}
FIELD_LINE = re.compile(r"^(" + "|".join(FIELDS) + r"):[ \t]*(.*)$")
NONE_FOUND = "No review decisions found."
DEVIATION_UNCHECKED = "Deviation: unchecked (no issue)."


class MalformedAnswerError(Exception):
    pass


def file_chunks(diff: str) -> list[tuple[str, str]]:
    """Return (path, chunk) per file, in diff order; the chunks rebuild the diff."""
    if not diff.startswith(FILE_HEADER):
        raise ScriptError(3, "DIFF does not start with a `diff --git` header")
    starts = [m.start() for m in re.finditer(r"^diff --git ", diff, flags=re.MULTILINE)]
    ends = [*starts[1:], len(diff)]
    return [(chunk_path(diff[s:e]), diff[s:e]) for s, e in zip(starts, ends, strict=True)]


def chunk_path(chunk: str) -> str:
    lines = chunk.splitlines()
    for line in lines:
        if line.startswith("+++ b/"):
            return line[len("+++ b/") :]
        if line.startswith("rename to "):
            return line[len("rename to ") :]
    for line in lines:
        if line.startswith("--- a/"):
            return line[len("--- a/") :]
    header = HEADER_PATHS.match(lines[0])
    if header is None:
        raise ScriptError(3, "a `diff --git` header names no a/ and b/ path")
    return header.group(2)


def pack(chunks: list[tuple[str, str]]) -> list[list[tuple[str, str]]]:
    batches: list[list[tuple[str, str]]] = []
    size = 0
    for path, chunk in chunks:
        chunk_bytes = len(chunk.encode())
        if not batches or size + chunk_bytes > MAX_BYTES:
            batches.append([])
            size = 0
        batches[-1].append((path, chunk))
        size += chunk_bytes
    return batches


def split(diff_file: Path, out: Path) -> dict:
    if not diff_file.is_file():
        raise ScriptError(2, "DIFF not found")
    batches = pack(file_chunks(diff_file.read_text(encoding="utf-8")))
    out.mkdir(parents=True, exist_ok=True)
    entries = []
    for number, batch in enumerate(batches, start=1):
        text = "".join(chunk for _, chunk in batch)
        name = f"batch-{number}.diff"
        (out / name).write_text(text, encoding="utf-8")
        size = len(text.encode())
        entries.append(
            {
                "batch": number,
                "file": name,
                "paths": [path for path, _ in batch],
                "bytes": size,
                "oversize": size > MAX_BYTES,
            }
        )
    manifest = {"max_bytes": MAX_BYTES, "batches": entries}
    (out / "batches.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def category_of(card: dict) -> str:
    return card.get("category", "").strip().lower().replace("behavior", "behaviour")


def strip_fence(text: str) -> list[str]:
    """The answer's lines, without a code fence the classifier wrapped around all of them."""
    lines = text.strip().splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return lines[1:-1]
    return lines


def parse_answer(text: str) -> tuple[list[dict], bool]:
    """Return one classifier answer's decision blocks and whether deviations were unchecked."""
    cards: list[dict] = []
    unchecked = False
    current: dict | None = None
    last_key: str | None = None
    for raw in strip_fence(text):
        line = raw.rstrip()
        if not line:
            current = None
        elif line == DEVIATION_UNCHECKED:
            unchecked = True
        elif line == NONE_FOUND:
            continue
        elif field := FIELD_LINE.match(line):
            if current is None:
                current = {}
                cards.append(current)
            last_key = FIELDS[field.group(1)]
            current[last_key] = field.group(2)
        elif current is not None and last_key is not None:
            current[last_key] += "\n" + line
        else:
            raise MalformedAnswerError("text outside a decision block")
    for card in cards:
        if category_of(card) not in CATEGORIES:
            raise MalformedAnswerError("unknown category")
        if not card.get("location"):
            raise MalformedAnswerError("decision without a location")
    return cards, unchecked


def location_file(location: str) -> str:
    return re.sub(r":\d+$", "", location.strip())


def queue_key(card: dict) -> tuple[int, int]:
    weakened = card.get("criterion", "").lower().startswith(WEAKENED_TEST)
    return CATEGORIES.index(category_of(card)), 0 if weakened else 1


def merge(out: Path) -> dict:
    manifest_file = out / "batches.json"
    if not manifest_file.is_file():
        raise ScriptError(2, "DIR holds no batches.json; run split first")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    batches = manifest["batches"]
    total = len(batches)
    batch_of = {path: b["batch"] for b in batches for path in b["paths"]}
    cards: list[dict] = []
    unclassified: list[dict] = []
    deviation = "checked"
    for batch in batches:
        number = batch["batch"]
        answer_file = out / f"batch-{number}.answer.md"
        failed_file = out / f"batch-{number}.failed"
        if failed_file.is_file():
            failure = failed_file.read_text(encoding="utf-8").strip().splitlines()
            reason = f"classifier run failed: {failure[0][:200] if failure else 'no reason given'}"
        elif not answer_file.is_file():
            reason = "no classifier answer"
            if batch["oversize"]:
                reason += (
                    f"; one file of {batch['bytes']} bytes,"
                    f" over the {manifest['max_bytes']}-byte limit"
                )
        else:
            try:
                found, unchecked = parse_answer(answer_file.read_text(encoding="utf-8"))
                reason = None
            except MalformedAnswerError as err:
                reason = f"classifier answer malformed: {err}"
        if reason is not None:
            unclassified += [{"path": p, "batch": number, "reason": reason} for p in batch["paths"]]
            continue
        if unchecked:
            deviation = "unchecked"
        for card in found:
            depends = card.get("depends_on")
            depends_elsewhere = (
                depends is not None and batch_of.get(location_file(depends), number) != number
            )
            card["batch"] = number
            card["unchecked_across_batches"] = total > 1 and (
                category_of(card) in SPAN_CATEGORIES or depends_elsewhere
            )
            cards.append(card)
    cards.sort(key=queue_key)
    return {
        "boundaries": [f"Batch {b['batch']} of {total}: {', '.join(b['paths'])}" for b in batches],
        "deviation": deviation,
        "cards": cards,
        "unclassified": unclassified,
    }


def main(argv: list[str]) -> int:
    parser = cli.parser(__doc__, "batches.py")
    commands = parser.add_subparsers(dest="command", required=True, metavar="{split,merge}")
    split_cmd = commands.add_parser("split")
    split_cmd.add_argument("diff", type=Path)
    split_cmd.add_argument("--out", required=True, type=Path)
    merge_cmd = commands.add_parser("merge")
    merge_cmd.add_argument("dir", type=Path)
    args = parser.parse_args(argv)
    if args.command == "split":
        return cli.run("batches.py", lambda: print(json.dumps(split(args.diff, args.out))))
    return cli.run("batches.py", lambda: print(json.dumps(merge(args.dir))))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
