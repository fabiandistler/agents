"""Strip markup an author can use to hide text from a human reader, and cap text.

Pull request text is untrusted. Before it reaches the review model, HTML
comments, CSS-hidden or ``hidden`` elements, zero-width characters and long
base64 blobs are removed, so the model sees what a human reviewer sees. In a
diff, a code file's HTML comment delimiters are neutralized instead, because a
person reads that file raw. The byte caps cut text without splitting a character or a line.
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
_FILE_SECTION = re.compile(r"(?m)^(?=diff --git )")
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


def _is_rendered_markdown(file_header: str) -> bool:
    """Whether a ``diff --git`` header names a Markdown file (git may quote the path)."""
    return file_header.rstrip().rstrip('"').lower().endswith(".md")


def _neutralize_html_comments(text: str) -> str:
    """Make HTML comment delimiters visible and inert: hyphens become U+2212."""
    return text.replace("<!--", "<!\u2212\u2212").replace("-->", "\u2212\u2212>")


def sanitize_diff(diff: str) -> tuple[str, bool]:
    """Sanitize a unified diff file by file; report whether anything was removed.

    A person reads a code file's diff as raw text, so an HTML comment in it
    hides nothing from them: its delimiters are neutralized and the model sees
    the content. Markdown renders the comment invisible, so a Markdown file's
    section, and any text before the first file header, go through
    ``sanitize_text`` unchanged. Neutralizing is not a removal.
    """
    sanitized, removed = [], False
    # Per file section, so an unclosed tag in one file cannot hide the next.
    for section in _FILE_SECTION.split(diff):
        if section.startswith("diff --git ") and not _is_rendered_markdown(
            section.split("\n", 1)[0]
        ):
            section = _neutralize_html_comments(section)
        cleaned = sanitize_text(section)
        removed = removed or cleaned != section
        sanitized.append(cleaned)
    return "".join(sanitized), removed


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
