#!/usr/bin/env python3
"""Place and read the review-decisions protocol, a Markdown file kept outside the repository.

usage: protocol.py path --repo DIR | protocol.py {resume,comment} FILE

  path --repo DIR  Print the absolute path for a new protocol under
                   $XDG_STATE_HOME/review-decisions/<repo>/ (default state home
                   ~/.local/state) and create that directory. Writes nothing in DIR.
  resume FILE      Print JSON: {"cards", "next", "later", "closed"}. "next" is
                   the first unanswered card not made moot (null if none),
                   "later" the cards answered `later`, "closed" whether the
                   closing line is present.
  comment FILE     Print one review comment, ready for the reviewer to post, that
                   joins the drafts of the cards answered `change` in card order.
                   Prints only; it posts nothing.

A card is a `## Card <n> of <total>` heading, its answer `- Answer: ok|change|later`,
its draft `- Draft comment: <text>` plus the indented lines after it.
exit codes: 0 ok; 1 usage error; 2 DIR not a git repository, or FILE missing;
3 FILE malformed (no cards, unknown answer, a `change` without a draft);
4 the state directory is inside DIR; 5 no card is answered `change`.

examples:
  python3 scripts/protocol.py path --repo .
  python3 scripts/protocol.py resume ~/.local/state/review-decisions/app/main-20260101T120000Z.md
  python3 scripts/protocol.py comment ~/.local/state/review-decisions/app/main-20260101T120000Z.md
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import cli
from cli import ScriptError, git

ANSWERS = {"ok", "change", "later"}
CLOSING = "Review decisions settled, no defect review."
CARD = re.compile(r"^## Card (\d+)\b")
ANSWER = re.compile(r"^- Answer:[ \t]*(\S*)[ \t]*$")
DRAFT = re.compile(r"^- Draft comment:[ \t]*(.*?)[ \t]*$")
MOOT = re.compile(r"^- Not reviewed:[ \t]*moot\b")
CONTINUATION = re.compile(r"^[ \t]+(\S.*?)[ \t]*$")
COMMENT_FOOTER = "This comment covers review decisions only; no defect review was done."


def state_home() -> Path:
    configured = os.environ.get("XDG_STATE_HOME")
    return Path(configured) if configured else Path.home() / ".local" / "state"


def new_protocol_path(repo: Path) -> Path:
    toplevel = git(repo, "rev-parse", "--show-toplevel")
    if toplevel is None:
        raise ScriptError(2, "--repo is not inside a git repository")
    root = Path(toplevel.strip()).resolve()
    ref = (
        git(repo, "symbolic-ref", "--short", "-q", "HEAD")
        or git(repo, "rev-parse", "--short", "HEAD")
        or "detached"
    ).strip()
    directory = (state_home() / "review-decisions" / root.name).resolve()
    if directory.is_relative_to(root):
        raise ScriptError(
            4, "the state directory lies inside the repository; set XDG_STATE_HOME elsewhere"
        )
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", ref).strip("-")
    return directory / f"{slug}-{stamp}.md"


@dataclass
class Card:
    answer: str | None = None
    draft: list[str] = field(default_factory=list)
    moot: bool = False


def read_cards(text: str) -> dict[int, Card]:
    """Map each card number to what the protocol records for it."""
    cards: dict[int, Card] = {}
    number = 0
    in_draft = False
    for line in text.splitlines():
        continuation = CONTINUATION.match(line)
        if in_draft and continuation:
            cards[number].draft.append(continuation.group(1))
            continue
        in_draft = False
        heading = CARD.match(line)
        if heading:
            number = int(heading.group(1))
            cards[number] = Card()
            continue
        if number not in cards:
            continue
        answer = ANSWER.match(line)
        if answer:
            value = answer.group(1)
            if value and value not in ANSWERS:
                raise ScriptError(3, f"card {number}: answer must be one of ok, change, later")
            cards[number].answer = value or None
            continue
        if MOOT.match(line):
            cards[number].moot = True
            continue
        draft = DRAFT.match(line)
        if draft:
            cards[number].draft = [draft.group(1)] if draft.group(1) else []
            in_draft = True
    if not cards:
        raise ScriptError(3, "no `## Card <n>` headings found")
    return cards


def resume_state(text: str) -> dict:
    cards = read_cards(text)
    answers = {n: card.answer for n, card in cards.items()}
    undecided = [n for n, card in cards.items() if card.answer is None and not card.moot]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return {
        "cards": len(answers),
        "next": undecided[0] if undecided else None,
        "later": [n for n, a in answers.items() if a == "later"],
        "closed": bool(lines) and lines[-1] == CLOSING,
    }


def combined_comment(text: str) -> str:
    """Join the drafts of the cards answered `change`, in card order, into one comment."""
    items = []
    for number, card in sorted(read_cards(text).items()):
        if card.answer != "change":
            continue
        if not card.draft:
            raise ScriptError(3, f"card {number}: answer change has no draft comment")
        items.append(card.draft)
    if not items:
        raise ScriptError(5, "no card is answered change; there is nothing to comment")
    lines = []
    for index, draft in enumerate(items, start=1):
        marker = f"{index}. "
        lines.append(marker + draft[0])
        lines.extend(" " * len(marker) + rest for rest in draft[1:])
    return "\n".join([*lines, "", COMMENT_FOOTER]) + "\n"


def command(args) -> None:
    if args.command == "path":
        print(new_protocol_path(args.repo))
        return
    if not args.file.is_file():
        raise ScriptError(2, "protocol file not found")
    text = args.file.read_text(encoding="utf-8")
    if args.command == "resume":
        print(json.dumps(resume_state(text)))
    else:
        print(combined_comment(text), end="")


def main(argv: list[str]) -> int:
    parser = cli.parser(__doc__, "protocol.py")
    commands = parser.add_subparsers(dest="command", required=True, metavar="{path,resume,comment}")
    path_cmd = commands.add_parser("path")
    path_cmd.add_argument("--repo", required=True, type=Path)
    for name in ("resume", "comment"):
        commands.add_parser(name).add_argument("file", type=Path)
    args = parser.parse_args(argv)
    return cli.run("protocol.py", lambda: command(args))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
