#!/usr/bin/env python3
"""Manage the review-decisions Markdown protocol outside the repository.

usage: protocol.py {path,init,add-card,answer,resume,close,comment,record-post} ...

  path --repo DIR  Print a new path under XDG_STATE_HOME (default ~/.local/state).
  init --repo DIR --base REF --cards FILE [--header-line TEXT] [--file-line TEXT]
                   Write the merged queue in input order. Both line flags repeat.
  add-card FILE --card-json CARD --file-line TEXT
                   Add a card from a single JSON object and update its file entry.
  answer FILE --card N [ok|change|later] [--draft TEXT] [--question TEXT --reply TEXT]
                   Record a decision or a question and reply. Pass multiline text as one argument.
  resume FILE      Print JSON with card count, next unanswered, later and closed.
  close FILE [--moot-remaining]
                   Mark the review settled. Use the flag after confirmed early stop.
  comment FILE [--json]
                   Print combined text or JSON with line comments and a summary.
  record-post FILE --target URL
                   Record a successful posting on the closed protocol.

exit codes: 0 ok; 1 usage; 2 repository or file missing; 3 invalid protocol or operation;
4 state directory inside the repository; 5 no change draft to comment.

examples:
  python3 scripts/protocol.py init --repo . --base main --cards merged.json
  python3 scripts/protocol.py answer protocol.md --card 1 change --draft 'Keep the existing key.'
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

import cli
from cli import ScriptError, git

ANSWERS = {"ok", "change", "later"}
CLOSING = "Review decisions settled, no defect review."
CARD = re.compile(r"^## Card (\d+)\b")
ANSWER = re.compile(r"^- Answer:[ \t]*(\S*)[ \t]*$")
DRAFT = re.compile(r"^- Draft comment:[ \t]*(.*)$")
MOOT = re.compile(r"^- Not reviewed:[ \t]*moot\b")
CONTINUATION = re.compile(r"^[ \t]+(\S.*?)[ \t]*$")
ANCHOR = "- Anchor: "
POSTED = "- Posted: "
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
    anchor: tuple[str, int] | None = None


def read_cards(text: str) -> dict[int, Card]:
    """Map each card number to what the protocol records for it."""
    cards: dict[int, Card] = {}
    number = 0
    in_draft = False
    for line in text.splitlines():
        if in_draft:
            if line.startswith("  "):
                cards[number].draft.append(line[2:])
                continue
            if continuation := CONTINUATION.match(line):
                cards[number].draft.append(continuation[1])
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
        if line.startswith(ANCHOR):
            anchor = read_json(line.removeprefix(ANCHOR), "anchor")
            if not isinstance(anchor, dict) or not valid_anchor(
                anchor.get("path"), anchor.get("line")
            ):
                raise ScriptError(3, f"card {number}: invalid anchor")
            cards[number].anchor = anchor["path"], anchor["line"]
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
    return {
        "cards": len(cards),
        "next": next(
            (number for number, card in cards.items() if not card.answer and not card.moot), None
        ),
        "later": [
            number for number, card in cards.items() if card.answer == "later" and not card.moot
        ],
        "closed": is_closed(text),
    }


def combined_comment(text: str) -> str:
    """Join the drafts of the cards answered `change`, in card order, into one comment."""
    return numbered_comment([card.draft for card in change_cards(text)])


def review_comment(text: str) -> dict:
    comments, summary = [], []
    for card in change_cards(text):
        if card.anchor is None:
            summary.append(card.draft)
        else:
            path, line = card.anchor
            comments.append({"path": path, "line": line, "body": "\n".join(card.draft)})
    return {"comments": comments, "summary": numbered_comment(summary)}


def init_protocol(
    repo: Path, base: str, queue_file: Path, headers: list[str], files: list[str]
) -> Path:
    queue = load_json(queue_file)
    if (
        not isinstance(queue, dict)
        or not isinstance(queue.get("cards"), list)
        or not queue["cards"]
    ):
        raise ScriptError(3, "cards file must contain a nonempty merged queue")
    total = len(queue["cards"])
    sections = [render_card(card, number, total) for number, card in enumerate(queue["cards"], 1)]
    path = new_protocol_path(repo)
    head = git(repo, "rev-parse", "HEAD")
    header = [
        "# Review decisions protocol",
        "",
        render_field("Repository", str(repo.resolve())),
        render_field("Base", base),
        render_field("Head", head.strip()) if head else "",
        *(render_field("Input", line) for line in headers),
        "",
        "A defect review was not run.",
        "The code-review skill was not run; this review does not depend on it.",
    ]
    file_lines = files or queue.get("files", [])
    if not isinstance(file_lines, list):
        raise ScriptError(3, "files must be a list")
    if file_lines:
        header.extend(["", "Files:", *(render_field("", line) for line in file_lines)])
    text = "\n".join(header) + "\n\n" + "\n\n".join(sections) + "\n"
    try:
        with path.open("x", encoding="utf-8") as protocol:
            protocol.write(text)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != text:
            raise ScriptError(3, "a different protocol already uses the new path") from None
    return path


def add_card(text: str, card: dict, file_line: str) -> str:
    ensure_open(text)
    recorded = read_cards(text)
    total = max(recorded) + 1
    section = render_card(card, total, total)
    path = card.get("location_path")
    if not isinstance(path, str) or not path or not file_line.startswith(f"{path}: "):
        raise ScriptError(3, "--file-line must start with the card's location_path and a colon")
    lines = text.rstrip("\n").splitlines()
    first_card = next(index for index, line in enumerate(lines) if CARD.match(line))
    header, cards = lines[:first_card], lines[first_card:]
    if "Files:" not in header:
        header.extend(["Files:", ""])
    start = header.index("Files:") + 1
    end = next((index for index in range(start, len(header)) if not header[index]), len(header))
    entry = render_field("", file_line)
    current_card = render_card(card, total - 1, total - 1)
    if entry in header[start:end] and f"\n{current_card}\n" in text:
        return text
    files = [
        line
        for line in header[start:end]
        if line != f"- {path}" and not line.startswith(f"- {path}: ")
    ]
    header[start:end] = [*files, entry]
    cards = [
        f"## Card {match[1]} of {total}" if (match := CARD.match(line)) else line for line in cards
    ]
    return "\n".join([*header, *cards, "", section, ""])


def answer_card(
    text: str,
    number: int,
    answer: str | None,
    draft: str | None,
    question: str | None,
    reply: str | None,
) -> str:
    paired = bool(question and question.strip()) and bool(reply and reply.strip())
    if (question is not None or reply is not None) and not paired:
        raise ScriptError(3, "--question and --reply must be supplied together")
    if answer is None and not paired:
        raise ScriptError(3, "supply an answer or a question and reply")
    if answer == "change" and (draft is None or not draft.strip()):
        raise ScriptError(3, "answer change requires --draft")
    if draft is not None and answer != "change":
        raise ScriptError(3, "--draft requires answer change")
    card = read_cards(text).get(number)
    if card is None or card.moot:
        raise ScriptError(3, f"card {number}: no open card at this number")
    draft = draft.strip() if draft is not None else None
    closed = is_closed(text)
    if closed and not (answer == card.answer == "change" and not card.draft and not paired):
        raise ScriptError(3, "protocol is already closed")
    different_draft = draft and card.draft and draft.splitlines() != card.draft
    if card.answer in {"ok", "change"} and (answer != card.answer or different_draft):
        raise ScriptError(3, f"card {number}: already has a final answer")
    entries = []
    if question and reply:
        entries.extend([render_field("Question", question), render_field("Reply", reply)])
    if answer is not None and answer != card.answer:
        entries.append(render_field("Answer", answer))
    if draft and (answer != card.answer or not card.draft):
        entries.append(render_field("Draft comment", draft))
    if not entries:
        return text
    if closed:
        text = text.rsplit(CLOSING, 1)[0]
    text = append_to_cards(text, {number: entries})
    return finish(text) if closed else text


def close_protocol(text: str, moot_remaining: bool) -> str:
    if is_closed(text):
        return text
    cards = read_cards(text)
    open_cards = {
        number: ["- Not reviewed: moot after reviewer confirmed early stop"]
        for number, card in cards.items()
        if card.answer not in {"ok", "change"} and not card.moot
    }
    if open_cards and not moot_remaining:
        raise ScriptError(3, "cards remain open; settle them or confirm early stop")
    if any(card.answer == "change" and not card.draft for card in cards.values()):
        raise ScriptError(3, "a card answered change still needs a draft")
    if open_cards:
        text = append_to_cards(text, open_cards)
    return finish(text)


def finish(text: str) -> str:
    return text.rstrip("\n") + "\n\n" + CLOSING + "\n"


def record_post(text: str, target: str) -> str:
    if not is_closed(text):
        raise ScriptError(3, "close the protocol before recording a post")
    change_cards(text)
    try:
        url = urlsplit(target)
    except ValueError:
        raise ScriptError(3, "--target must be a post URL") from None
    if (
        url.scheme not in {"https", "http"}
        or not url.netloc
        or any(char.isspace() for char in target)
    ):
        raise ScriptError(3, "--target must be a post URL")
    if any(line.startswith(POSTED) and line.endswith(" " + target) for line in text.splitlines()):
        return text
    before_close, _ = text.rstrip().rsplit(CLOSING, 1)
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    before_close = before_close.rstrip("\n")
    return finish(f"{before_close}\n\n{POSTED}{timestamp} {target}")


def valid_anchor(path, line) -> bool:
    return isinstance(path, str) and bool(path) and type(line) is int and line > 0


def is_closed(text: str) -> bool:
    lines = text.rstrip("\n").splitlines()
    return bool(lines) and lines[-1] == CLOSING


def ensure_open(text: str) -> None:
    if is_closed(text):
        raise ScriptError(3, "protocol is already closed")


def read_json(text: str, label: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise ScriptError(3, f"{label} must contain valid JSON") from None


def load_json(path: Path):
    if not path.is_file():
        raise ScriptError(2, "card JSON file not found")
    return read_json(path.read_text(encoding="utf-8"), "card file")


def render_field(label: str, text: str) -> str:
    if not isinstance(text, str):
        raise ScriptError(3, "protocol field values must be text")
    lines = text.splitlines() or [""]
    marker = f"- {label}: " if label else "- "
    return "\n".join([marker + lines[0], *("  " + line for line in lines[1:])])


def render_card(card: dict, number: int, total: int) -> str:
    if not isinstance(card, dict) or not isinstance(card.get("location"), str):
        raise ScriptError(3, f"card {number}: missing location text")
    fields = [f"## Card {number} of {total}", "", render_field("Location", card["location"])]
    path, line = card.get("location_path"), card.get("location_line")
    if card.get("location_verified") is True and card.get("location_changed") is True:
        if not valid_anchor(path, line):
            raise ScriptError(3, f"card {number}: invalid anchor")
        fields.append(ANCHOR + json.dumps({"path": path, "line": line}))
    for key, label in (
        ("category", "Category"),
        ("criterion", "Criterion"),
        ("chosen", "Chosen"),
        ("cost_to_undo", "Cost to undo after merge"),
        ("lean", "Lean"),
        ("depends_on", "Depends on"),
        ("location_reason", "Location unverified"),
    ):
        if card.get(key):
            fields.append(render_field(label, card[key]))
    if card.get("nearest_line") is not None:
        fields.append(render_field("Nearest changed line", str(card["nearest_line"])))
    if card.get("unchecked_across_batches"):
        fields.append("- Unchecked across batches")
    return "\n".join(fields)


def append_to_cards(text: str, entries: dict[int, list[str]]) -> str:
    lines = text.rstrip("\n").splitlines()
    sections = [
        (index, int(match[1])) for index, line in enumerate(lines) if (match := CARD.match(line))
    ]
    end = len(lines)
    for start, number in reversed(sections):
        if entries.get(number):
            while end > start + 1 and not lines[end - 1]:
                end -= 1
            entry_lines = "\n".join(entries[number]).splitlines()
            if lines[end - len(entry_lines) : end] != entry_lines:
                lines[end:end] = entry_lines
        end = start
    return "\n".join(lines) + "\n"


def change_cards(text: str) -> list[Card]:
    cards = []
    for number, card in sorted(read_cards(text).items()):
        if card.answer == "change" and not card.moot:
            if not card.draft:
                raise ScriptError(3, f"card {number}: answer change has no draft comment")
            cards.append(card)
    if not cards:
        raise ScriptError(5, "no card is answered change; there is nothing to comment")
    return cards


def numbered_comment(items: list[list[str]]) -> str:
    lines = []
    for index, draft in enumerate(items, start=1):
        marker = f"{index}. "
        lines.append(marker + draft[0])
        lines.extend(" " * len(marker) + rest for rest in draft[1:])
    if lines:
        lines.append("")
    return "\n".join([*lines, COMMENT_FOOTER]) + "\n"


def update_protocol(path: Path, text: str) -> None:
    # Atomic replacement keeps readers from seeing a partly written card.
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as changed:
        replacement = Path(changed.name)
        try:
            changed.write(text)
            changed.close()
            replacement.replace(path)
        finally:
            replacement.unlink(missing_ok=True)


def command(args) -> None:
    if args.command == "path":
        print(new_protocol_path(args.repo))
        return
    if args.command == "init":
        print(init_protocol(args.repo, args.base, args.cards, args.header_line, args.file_line))
        return
    if not args.file.is_file():
        raise ScriptError(2, "protocol file not found")
    text = args.file.read_text(encoding="utf-8")
    match args.command:
        case "resume":
            print(json.dumps(resume_state(text)))
            return
        case "comment":
            print(
                json.dumps(review_comment(text)) if args.json else combined_comment(text),
                end="\n" if args.json else "",
            )
            return
        case "add-card":
            updated = add_card(text, load_json(args.card_json), args.file_line)
        case "answer":
            updated = answer_card(
                text, args.card, args.answer, args.draft, args.question, args.reply
            )
        case "close":
            updated = close_protocol(text, args.moot_remaining)
        case "record-post":
            updated = record_post(text, args.target)
    if updated != text:
        update_protocol(args.file, updated)


def main(argv: list[str]) -> int:
    parser = cli.parser(__doc__, "protocol.py")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("path").add_argument("--repo", required=True, type=Path)
    init = commands.add_parser("init")
    init.add_argument("--repo", required=True, type=Path)
    init.add_argument("--base", required=True)
    init.add_argument("--cards", required=True, type=Path)
    init.add_argument("--header-line", action="append", default=[])
    init.add_argument("--file-line", action="append", default=[])
    add = commands.add_parser("add-card")
    add.add_argument("--card-json", required=True, type=Path)
    add.add_argument("--file-line", required=True)
    answer = commands.add_parser("answer")
    answer.add_argument("file", type=Path)
    answer.add_argument("--card", required=True, type=int)
    answer.add_argument("answer", nargs="?", choices=sorted(ANSWERS))
    answer.add_argument("--draft")
    answer.add_argument("--question")
    answer.add_argument("--reply")
    close = commands.add_parser("close")
    close.add_argument("--moot-remaining", action="store_true")
    comment = commands.add_parser("comment")
    comment.add_argument("--json", action="store_true")
    post = commands.add_parser("record-post")
    post.add_argument("--target", required=True)
    commands.add_parser("resume").add_argument("file", type=Path)
    for verb in (add, close, comment, post):
        verb.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    return cli.run("protocol.py", lambda: command(args))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
