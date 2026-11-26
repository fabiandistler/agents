"""Render the review comment from the drafts of the cards answered `change`.

Each card carries `draft` (its lines) and `anchor` (`(path, line)` on an added
line, or None). protocol.py reads the cards from the protocol and passes them
in card order; this module only shapes the text the forge receives.
"""

from __future__ import annotations

COMMENT_FOOTER = "This comment covers review decisions only; no defect review was done."


def combined_comment(cards: list) -> str:
    """Join the drafts, in card order, into one comment."""
    return numbered_comment([card.draft for card in cards])


def review_comment(cards: list) -> dict:
    comments, summary = [], []
    for card in cards:
        if card.anchor is None:
            summary.append(card.draft)
        else:
            path, line = card.anchor
            comments.append({"path": path, "line": line, "body": "\n".join(card.draft)})
    return {"comments": comments, "summary": numbered_comment(summary)}


def numbered_comment(items: list[list[str]]) -> str:
    lines = []
    for index, draft in enumerate(items, start=1):
        marker = f"{index}. "
        lines.append(marker + draft[0])
        lines.extend(" " * len(marker) + rest for rest in draft[1:])
    if lines:
        lines.append("")
    return "\n".join([*lines, COMMENT_FOOTER]) + "\n"
