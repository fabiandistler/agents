"""The handoff protocol: the facts factory runs hand each other through GitHub.

A runner keeps nothing, so one run tells the next what happened through
comment markers on GitHub (docs/factory/architecture.md, "Data flow"). This
module owns those facts: who counts as the factory's own author, and the text
of each marker. ``format_marker`` writes a marker; ``read_markers`` reads them
back, and only from entries the workflow bot wrote, so a marker a person
quotes is just text.

Pure and standard library only; it imports no other factory module. The
marker texts are a contract with comments already stored on GitHub: a changed
byte resets a counter or duplicates a comment.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

# The login the workflow's GITHUB_TOKEN writes as. Only its markers count.
WORKFLOW_BOT_LOGIN = "github-actions[bot]"
# The login the Claude GitHub App writes as: the implementer's and Rework's
# pull requests and replies.
APP_LOGIN = "claude[bot]"

_HEAD = r"[0-9a-f]{40}"
_ROUND = r"[1-9][0-9]*"


def _round(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _head(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(_HEAD, value) is not None


@dataclass(frozen=True)
class MarkerKind:
    """One marker: its text template, the pattern that reads it, and its field rules."""

    name: str
    template: str
    pattern: re.Pattern[str]
    fields: Mapping[str, Callable[[object], bool]]
    parsers: Mapping[str, Callable[[str], object]]


# `<!-- rework-round:<round> head:<head> -->`: one per Rework run, on the pull request.
REWORK_ROUND = MarkerKind(
    name="rework round",
    template="<!-- rework-round:{round} head:{head} -->",
    pattern=re.compile(rf"<!-- rework-round:(?P<round>{_ROUND}) head:(?P<head>{_HEAD}) -->"),
    fields={"round": _round, "head": _head},
    parsers={"round": int, "head": str},
)
# `<!-- rework-handoff head:<head> -->`: the pull request went to a person for this head.
REWORK_HANDOFF = MarkerKind(
    name="rework handoff",
    template="<!-- rework-handoff head:{head} -->",
    pattern=re.compile(rf"<!-- rework-handoff head:(?P<head>{_HEAD}) -->"),
    fields={"head": _head},
    parsers={"head": str},
)


@dataclass(frozen=True)
class MarkerRead:
    """One bot-authored entry and the fields of each of its markers, in text order."""

    entry: Mapping[str, object]
    markers: tuple[dict[str, object], ...]


def format_marker(kind: MarkerKind, **fields: object) -> str:
    """The marker text for ``fields``; ``ValueError`` when a field breaks the kind's grammar."""
    if set(fields) != set(kind.fields):
        raise ValueError(f"{kind.name} marker takes the fields {sorted(kind.fields)}")
    for name, valid in kind.fields.items():
        if not valid(fields[name]):
            raise ValueError(f"{kind.name} marker field '{name}' is malformed")
    return kind.template.format(**fields)


def read_markers(kind: MarkerKind, entries: Sequence[object]) -> list[MarkerRead]:
    """Each entry by the workflow bot holding a well-formed ``kind`` marker, in entry order.

    An entry is a mapping with ``author`` and ``body``, as
    ``pr_github.comment_entry`` builds it. Entries by anyone else, entries
    without a string body and malformed markers contribute nothing.
    """
    reads: list[MarkerRead] = []
    for entry in entries:
        if not isinstance(entry, Mapping) or entry.get("author") != WORKFLOW_BOT_LOGIN:
            continue
        body = entry.get("body")
        if not isinstance(body, str):
            continue
        markers = tuple(
            {name: kind.parsers[name](match[name]) for name in kind.fields}
            for match in kind.pattern.finditer(body)
        )
        if markers:
            reads.append(MarkerRead(entry, markers))
    return reads
