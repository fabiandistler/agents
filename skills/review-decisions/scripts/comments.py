"""Render the review comment from the drafts of the cards answered `change`.

Each card carries `draft` (its lines) and `anchor` (`(path, line)` on an added
line, or None). protocol.py reads the cards from the protocol and passes them
in card order; this module only shapes the text the forge receives.
"""

from __future__ import annotations

import re

COMMENT_FOOTER = "This comment covers review decisions only; no defect review was done."


def combined_comment(cards: list) -> str:
    """Join the drafts, in card order, into one comment."""
    return f"{numbered_drafts([card.draft for card in cards])}\n{COMMENT_FOOTER}\n"


def review_comment(cards: list) -> dict:
    """Split the drafts into line comments and a summary; the footer stays a field of its own."""
    comments, summary = [], []
    for card in cards:
        if card.anchor is None:
            summary.append(card.draft)
        else:
            path, line = card.anchor
            comments.append(
                {"path": path, "line": line, "body": line_comment(card.draft, path, line)}
            )
    return {
        "comments": comments,
        "summary": numbered_drafts(summary) if summary else None,
        "footer": COMMENT_FOOTER,
    }


def line_comment(draft: list[str], path: str, line: int) -> str:
    """Drop a leading `path:line` that repeats the anchor; its `(topic)` becomes a bold heading."""
    repeated = re.match(
        rf"(`?){re.escape(path)}:{line}(?!\d)(?:\s*\(([^()]*)\))?\1"
        rf"(?:\s*\(([^()]*)\))?\s*:?\s*(.*)$",
        draft[0],
    )
    if repeated is None:
        return "\n".join(draft)
    topic = (repeated[2] or repeated[3] or "").strip()
    body = [repeated[4], *draft[1:]]
    while body and not body[0].strip():
        body.pop(0)
    if topic:
        return "\n".join([f"**{topic}**", *([""] + body if body else [])])
    # A draft that is only its location has nothing else to say; keep it whole.
    return "\n".join(body) if body else "\n".join(draft)


def numbered_drafts(items: list[list[str]]) -> str:
    lines = []
    for index, draft in enumerate(items, start=1):
        marker = f"{index}. "
        lines.append(marker + draft[0])
        lines.extend(" " * len(marker) + rest for rest in draft[1:])
    return "".join(line + "\n" for line in lines)
