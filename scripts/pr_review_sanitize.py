"""Strip markup an author can use to hide text from a human reader, and cap text.

Pull request text is untrusted. Before it reaches the review model, HTML
comments, CSS-hidden or ``hidden`` elements, zero-width characters and long
base64 blobs are removed, so the model sees what a human reviewer sees. The
byte caps cut text without splitting a character or a line.
"""

from __future__ import annotations

import re

_ZERO_WIDTH = str.maketrans("", "", "\u200b\u200c\u200d\u2060\ufeff")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_HTML_COMMENT_UNCLOSED = re.compile(r"<!--.*\Z", re.DOTALL)
_HIDDEN_ELEMENT = re.compile(
    r"<(?P<tag>[A-Za-z][A-Za-z0-9]*)\b(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL,
)
_HIDDEN_ATTR = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|(?<=\s)hidden(?=\s|=|>|/|$)",
    re.IGNORECASE,
)
_HIDDEN_OPEN = re.compile(r"<(?P<tag>[A-Za-z][A-Za-z0-9]*)\b(?P<attrs>[^>]*)>", re.IGNORECASE)
_BASE64 = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{200,}={0,2}(?![A-Za-z0-9+/=])")


def _remove_hidden_elements(text: str) -> str:
    """Remove elements whose opening tag marks them as hidden."""

    def replacement(match: re.Match[str]) -> str:
        return "" if _HIDDEN_ATTR.search(match.group("attrs")) else match.group(0)

    previous = None
    while previous != text:
        previous = text
        text = _HIDDEN_ELEMENT.sub(replacement, text)
    # A tag the author never closed hides everything the renderer puts inside
    # it, so drop the remainder. Missing the text is safer than trusting it.
    for match in _HIDDEN_OPEN.finditer(text):
        if not _HIDDEN_ATTR.search(match.group("attrs")):
            continue
        closing = re.search(rf"</{match.group('tag')}\s*>", text[match.end() :], re.IGNORECASE)
        if closing is None:
            return text[: match.start()]
    return text


def sanitize_text(text: str) -> str:
    """Strip markup an author can use to hide text from a human reader."""
    text = text.translate(_ZERO_WIDTH)
    text = _HTML_COMMENT.sub("", text)
    text = _HTML_COMMENT_UNCLOSED.sub("", text)
    text = _remove_hidden_elements(text)
    return _BASE64.sub("", text)


def truncate_bytes(text: str, limit: int) -> str:
    """Cut UTF-8 text to a byte budget without splitting a character or a line."""
    if limit <= 0:
        return ""
    data = text.encode("utf-8")
    if len(data) <= limit:
        return text
    cut = data[:limit].decode("utf-8", errors="ignore")
    newline = cut.rfind("\n")
    return cut[:newline] if newline > 0 else cut


def truncate_text(text: str, limit: int) -> tuple[str, bool]:
    """``truncate_bytes`` and whether it cut anything."""
    capped = truncate_bytes(text, limit)
    return capped, capped != text


def single_line(text: str, limit: int) -> str:
    """Sanitized ``text`` on one line, within ``limit`` bytes."""
    return truncate_bytes(" ".join(sanitize_text(text).split()), limit)
