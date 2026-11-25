#!/usr/bin/env python3
"""Place and read the review-decisions protocol, a Markdown file kept outside the repository.

usage: protocol.py path --repo DIR | protocol.py resume FILE

  path --repo DIR  Print the absolute path for a new protocol under
                   $XDG_STATE_HOME/review-decisions/<repo>/ (default state home
                   ~/.local/state) and create that directory. Writes nothing in DIR.
  resume FILE      Print JSON for a protocol: {"cards", "next", "later", "closed"}.
                   "next" is the first card without an answer (null if none),
                   "later" the cards answered `later`, "closed" whether the
                   closing line is present.

A card is a `## Card <n> of <total>` heading; its answer is the line
`- Answer: ok|change|later`. A card with no answer, or with only questions, is undecided.

exit codes: 0 ok; 1 usage error; 2 DIR not a git repository, or FILE missing;
3 FILE malformed (no cards, unknown answer); 4 the state directory is inside DIR.

examples:
  python3 scripts/protocol.py path --repo .
  python3 scripts/protocol.py resume ~/.local/state/review-decisions/app/main-20260101T120000Z.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ANSWERS = {"ok", "change", "later"}
CLOSING = "Review decisions settled, no defect review."
CARD = re.compile(r"^## Card (\d+)\b")
ANSWER = re.compile(r"^- Answer:[ \t]*(\S*)[ \t]*$")


class ProtocolError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def git(repo: Path, *args: str) -> str | None:
    proc = subprocess.run(  # noqa: S603 -- fixed Git argv; no shell.
        ["git", "-C", str(repo), *args],  # noqa: S607 -- Git intentionally resolves from PATH.
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def state_home() -> Path:
    configured = os.environ.get("XDG_STATE_HOME")
    return Path(configured) if configured else Path.home() / ".local" / "state"


def new_protocol_path(repo: Path) -> Path:
    toplevel = git(repo, "rev-parse", "--show-toplevel")
    if toplevel is None:
        raise ProtocolError(2, "--repo is not inside a git repository")
    root = Path(toplevel).resolve()
    ref = (
        git(repo, "symbolic-ref", "--short", "-q", "HEAD")
        or git(repo, "rev-parse", "--short", "HEAD")
        or "detached"
    )
    directory = (state_home() / "review-decisions" / root.name).resolve()
    if directory.is_relative_to(root):
        raise ProtocolError(
            4, "the state directory lies inside the repository; set XDG_STATE_HOME elsewhere"
        )
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", ref).strip("-")
    return directory / f"{slug}-{stamp}.md"


def resume_state(text: str) -> dict:
    answers: dict[int, str | None] = {}
    current: int | None = None
    for line in text.splitlines():
        heading = CARD.match(line)
        if heading:
            current = int(heading.group(1))
            answers[current] = None
            continue
        answer = ANSWER.match(line)
        if answer and current is not None:
            value = answer.group(1)
            if value and value not in ANSWERS:
                raise ProtocolError(3, f"card {current}: answer must be one of ok, change, later")
            answers[current] = value or None
    if not answers:
        raise ProtocolError(3, "no `## Card <n>` headings found")
    undecided = [n for n, a in answers.items() if a is None]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return {
        "cards": len(answers),
        "next": undecided[0] if undecided else None,
        "later": [n for n, a in answers.items() if a == "later"],
        "closed": bool(lines) and lines[-1] == CLOSING,
    }


class Parser(argparse.ArgumentParser):
    def error(self, message: str):
        self.print_usage(sys.stderr)
        self.exit(1, f"protocol.py: {message}\n")


def main(argv: list[str]) -> int:
    parser = Parser(
        prog="protocol.py",
        usage="protocol.py path --repo DIR | protocol.py resume FILE",
        description=__doc__.split("\n", 3)[3],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="{path,resume}")
    path_cmd = commands.add_parser("path")
    path_cmd.add_argument("--repo", required=True, type=Path)
    resume_cmd = commands.add_parser("resume")
    resume_cmd.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "path":
            print(new_protocol_path(args.repo))
        else:
            if not args.file.is_file():
                raise ProtocolError(2, "protocol file not found")
            print(json.dumps(resume_state(args.file.read_text(encoding="utf-8"))))
    except ProtocolError as err:
        print(f"protocol.py: {err}", file=sys.stderr)
        return err.code
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
