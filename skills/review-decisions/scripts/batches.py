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
                        {"boundaries", "deviation", "files", "cards", "unclassified"}.
                        Cards keep the category order, batch and diff location.
                        "unclassified" lists files without readable answers
                        and why: the line in DIR/batch-<k>.failed, or the size.

exit codes: 0 ok; 1 usage error; 2 DIFF or DIR/batches.json missing;
3 DIFF is not a git diff.

examples:
  python3 scripts/batches.py split /tmp/rd/diff.patch --out /tmp/rd/batches
  python3 scripts/batches.py merge /tmp/rd/batches
"""

from __future__ import annotations

import codecs
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cli
from cli import ScriptError

MAX_BYTES = 200_000
FILE_HEADER = "diff --git "
HEADER_PATHS = re.compile(r'^diff --git (?:a/.*|"a/(?:[^"\\]|\\.)*") (b/.*|"b/(?:[^"\\]|\\.)*")$')
HUNK_HEADER = re.compile(r"^@@ -[0-9]+(?:,[0-9]+)? \+([0-9]+)(?:,([0-9]+))? @@")
LOCATION_LINE = re.compile(r"^(.+):([0-9]+)$")

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
    "Cost to undo": "cost_to_undo",
    "Lean": "lean",
    "Depends on": "depends_on",
}
FIELD_LINE = re.compile(r"^(" + "|".join(FIELDS) + r"):[ \t]*(.*)$")
NONE_FOUND = "No review decisions found."
DEVIATION_UNCHECKED = "Deviation: unchecked (no issue)."


def file_chunks(diff: str) -> list[tuple[str, str]]:
    """Return (path, chunk) per file, in diff order; the chunks rebuild the diff."""
    if not diff.startswith(FILE_HEADER):
        raise ScriptError(3, "DIFF does not start with a `diff --git` header")
    starts = [m.start() for m in re.finditer(r"^diff --git ", diff, flags=re.MULTILINE)]
    ends = [*starts[1:], len(diff)]
    return [(chunk_path(diff[s:e]), diff[s:e]) for s, e in zip(starts, ends)]


def chunk_path(chunk: str) -> str:
    header, *metadata = chunk.split("\n")
    old_path = None
    for line in metadata:
        if line.startswith("@@"):
            break
        if line.startswith(("+++ b/", '+++ "b/')):
            return unquote_path(line[4:])[2:]
        if line.startswith("rename to "):
            return unquote_path(line[len("rename to ") :])
        if line.startswith(("--- a/", '--- "a/')):
            old_path = unquote_path(line[4:])[2:]
    if old_path is not None:
        return old_path
    paths = HEADER_PATHS.match(header)
    if paths is None:
        raise ScriptError(3, "a `diff --git` header names no a/ and b/ path")
    return unquote_path(paths.group(1))[2:]


def unquote_path(path: str) -> str:
    path = path.removesuffix("\t")
    if path.startswith('"') and path.endswith('"'):
        return codecs.escape_decode(path[1:-1].encode())[0].decode()
    return path


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


@dataclass
class Decision:
    """One review decision from a classifier answer, as merge prints it."""

    category: str = ""
    location: str = ""
    criterion: str = ""
    chosen: str = ""
    cost_to_undo: str = ""
    lean: str = ""
    depends_on: str | None = None
    batch: int = field(default=0, init=False)
    unchecked_across_batches: bool = field(default=False, init=False)
    location_path: str | None = field(default=None, init=False)
    location_line: int | None = field(default=None, init=False)
    location_verified: bool = field(default=False, init=False)
    location_changed: bool = field(default=False, init=False)
    location_reason: str | None = field(default=None, init=False)
    nearest_line: int | None = field(default=None, init=False)

    @property
    def kind(self) -> str:
        return self.category.strip().lower().replace("behavior", "behaviour")

    def queue_key(self) -> tuple[int, int]:
        weakened = self.criterion.lower().startswith(WEAKENED_TEST)
        return CATEGORIES.index(self.kind), 0 if weakened else 1

    def may_span(self, batch_of: dict[str, int]) -> bool:
        """Whether the decision's other half may sit in a batch other than its own."""
        if self.kind in SPAN_CATEGORIES:
            return True
        if self.depends_on is None:
            return False
        return batch_of.get(location_file(self.depends_on), self.batch) != self.batch

    def verify_location(self, diff_lines: dict[str, dict[int, bool]] | None) -> None:
        location = self.location.strip()
        if location == "-":
            self.location_reason = "omission has no location"
            return
        self.location_path = location_file(location)
        match = LOCATION_LINE.fullmatch(location)
        location_line = (int(match.group(2)) or None) if match else None
        self.location_line = location_line
        if diff_lines is None:
            self.location_reason = "batch diff unavailable"
        elif self.location_path not in diff_lines:
            self.location_reason = "file not in diff"
        elif location_line is None:
            self.location_reason = "location has no line"
        else:
            new_side = diff_lines[self.location_path]
            if location_line in new_side:
                self.location_verified = True
                self.location_changed = new_side[location_line]
            else:
                self.location_reason = "line outside every hunk"
                self.nearest_line = min(
                    (line for line, added in new_side.items() if added),
                    key=lambda line: (abs(line - location_line), line),
                    default=None,
                )

    def as_json(self) -> dict:
        fields = asdict(self)
        if self.depends_on is None:
            del fields["depends_on"]
        return fields


class UnclassifiedBatchError(Exception):
    """A batch has no usable classifier answer; the message is the reason."""


def strip_fence(text: str) -> list[str]:
    """The answer's lines, without a code fence the classifier wrapped around all of them."""
    lines = text.strip().splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return lines[1:-1]
    return lines


def answer_blocks(text: str) -> list[list[str]]:
    """The answer's runs of non-blank lines."""
    blocks: list[list[str]] = [[]]
    for raw in strip_fence(text):
        line = raw.rstrip()
        if line:
            blocks[-1].append(line)
        elif blocks[-1]:
            blocks.append([])
    return [block for block in blocks if block]


def parse_decision(lines: list[str]) -> Decision:
    fields: dict[str, str] = {}
    key: str | None = None
    discarding_alternatives = False
    for line in lines:
        if field_line := FIELD_LINE.match(line):
            discarding_alternatives = False
            key = FIELDS[field_line.group(1)]
            fields[key] = field_line.group(2)
        elif line.startswith("Alternatives:"):
            discarding_alternatives = True
        elif discarding_alternatives:
            continue
        elif key is None:
            raise UnclassifiedBatchError(
                "classifier answer malformed: text outside a decision block"
            )
        else:
            fields[key] += "\n" + line
    decision = Decision(**fields)
    if decision.kind not in CATEGORIES:
        raise UnclassifiedBatchError("classifier answer malformed: unknown category")
    if not decision.location:
        raise UnclassifiedBatchError("classifier answer malformed: decision without a location")
    return decision


def parse_answer(text: str) -> tuple[list[Decision], bool]:
    """Return one classifier answer's decisions and whether deviations were unchecked."""
    decisions = []
    unchecked = False
    for block in answer_blocks(text):
        unchecked = unchecked or DEVIATION_UNCHECKED in block
        lines = [line for line in block if line not in (DEVIATION_UNCHECKED, NONE_FOUND)]
        if lines:
            decisions.append(parse_decision(lines))
    return decisions, unchecked


def location_file(location: str) -> str:
    match = LOCATION_LINE.fullmatch(location.strip())
    return match.group(1) if match else location.strip()


def new_side_lines(chunk: str) -> dict[int, bool]:
    """Map right-side hunk lines to whether they were added."""
    lines: dict[int, bool] = {}
    end = number = 0
    for line in chunk.split("\n"):
        if hunk := HUNK_HEADER.match(line):
            number = int(hunk.group(1))
            end = number + int(hunk.group(2) or "1")
        elif number < end and line.startswith((" ", "+")):
            lines[number] = line.startswith("+")
            number += 1
    return lines


def read_batch_answer(out: Path, batch: dict, max_bytes: int) -> tuple[list[Decision], bool]:
    """The decisions of one batch, or UnclassifiedBatchError naming why there are none."""
    number = batch["batch"]
    failed_file = out / f"batch-{number}.failed"
    answer_file = out / f"batch-{number}.answer.md"
    if failed_file.is_file():
        failure = failed_file.read_text(encoding="utf-8").strip().splitlines()
        reason = failure[0][:200] if failure else "no reason given"
        raise UnclassifiedBatchError(f"classifier run failed: {reason}")
    if not answer_file.is_file():
        reason = "no classifier answer"
        if batch["oversize"]:
            reason += f"; one file of {batch['bytes']} bytes, over the {max_bytes}-byte limit"
        raise UnclassifiedBatchError(reason)
    decisions, unchecked = parse_answer(answer_file.read_text(encoding="utf-8"))
    for decision in decisions:
        decision.batch = number
    return decisions, unchecked


def merge(out: Path) -> dict:
    manifest_file = out / "batches.json"
    if not manifest_file.is_file():
        raise ScriptError(2, "DIR holds no batches.json; run split first")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    batches = manifest["batches"]
    total = len(batches)
    batch_of = {path: b["batch"] for b in batches for path in b["paths"]}
    decisions: list[Decision] = []
    unclassified: list[dict] = []
    deviation = "checked"
    for batch in batches:
        try:
            found, unchecked = read_batch_answer(out, batch, manifest["max_bytes"])
        except UnclassifiedBatchError as err:
            unclassified += [
                {"path": path, "batch": batch["batch"], "reason": str(err)}
                for path in batch["paths"]
            ]
            continue
        if unchecked:
            deviation = "unchecked"
        if not found:
            continue
        diff_file = out / batch["file"]
        diff_lines = None
        if diff_file.is_file():
            diff_lines = {
                path: new_side_lines(chunk)
                for path, chunk in file_chunks(diff_file.read_text(encoding="utf-8"))
            }
        for decision in found:
            decision.verify_location(diff_lines)
            decision.unchecked_across_batches = total > 1 and decision.may_span(batch_of)
        decisions += found
    decisions.sort(key=Decision.queue_key)
    return {
        "boundaries": [f"Batch {b['batch']} of {total}: {', '.join(b['paths'])}" for b in batches],
        "deviation": deviation,
        "files": list(batch_of),
        "cards": [decision.as_json() for decision in decisions],
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
