"""Split masked German text into sentences, the unit style_scan.py counts in.

Code blocks, inline code and URLs are blanked out first (`mask`), so they count
as neither words nor sentence ends. `split_sentences` then cuts paragraphs,
list items and headings, and decides at each period whether it ends a
sentence or belongs to an abbreviation, an initial, an ordinal or a date.
Offsets stay those of the original text. Stdlib only; Python 3.11+.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

LETTER = "A-Za-zÄÖÜäöüßÀ-ÖØ-öø-ÿ"
WORD = re.compile(rf"[{LETTER}0-9]+(?:[-'’][{LETTER}0-9]+)*")

# Abbreviations whose period does not end a sentence. Normalised: lowercase,
# spaces removed, so "z. B." and "z.B." both become "z.b.".
ABBREVIATIONS = frozenset(
    [
        "z.b.",
        "d.h.",
        "u.a.",
        "o.ä.",
        "u.u.",
        "z.t.",
        "s.o.",
        "s.u.",
        "u.ä.",
        "i.d.r.",
        "m.e.",
        "v.a.",
        "o.g.",
        "a.d.",
        "usw.",
        "bzw.",
        "etc.",
        "vgl.",
        "ca.",
        "nr.",
        "bspw.",
        "evtl.",
        "ggf.",
        "inkl.",
        "exkl.",
        "zzgl.",
        "sog.",
        "ggü.",
        "dr.",
        "prof.",
        "hr.",
        "fr.",
        "st.",
        "abs.",
        "art.",
        "kap.",
        "jh.",
        "jhd.",
        "mio.",
        "mrd.",
        "tsd.",
        "max.",
        "min.",
        "tel.",
        "str.",
        "bd.",
        "hrsg.",
        "aufl.",
        "ebd.",
        "allg.",
        "insb.",
        "ugs.",
        "gem.",
        "lt.",
        "u.",
        "o.",
        "abb.",
        "tab.",
        "jan.",
        "feb.",
        "febr.",
        "mär.",
        "apr.",
        "jun.",
        "jul.",
        "aug.",
        "sep.",
        "sept.",
        "okt.",
        "nov.",
        "dez.",
    ]
)
SENTENCE_FINAL_ABBREVIATIONS = frozenset({"usw.", "etc.", "u.ä.", "o.ä."})
MONTHS = frozenset(
    [
        "januar",
        "februar",
        "märz",
        "april",
        "mai",
        "juni",
        "juli",
        "august",
        "september",
        "oktober",
        "november",
        "dezember",
    ]
)
# A number + period after one of these words is an ordinal ("am 3. Oktober").
ORDINAL_CONTEXT = frozenset(
    [
        "der",
        "die",
        "das",
        "den",
        "dem",
        "des",
        "am",
        "im",
        "zum",
        "zur",
        "vom",
        "beim",
        "ab",
        "bis",
        "seit",
        "vor",
        "nach",
        "ein",
        "eine",
        "einen",
        "einem",
        "einer",
        "jeder",
        "jede",
        "jedes",
        "ihr",
        "ihre",
        "sein",
        "seine",
        "mein",
        "meine",
        "unser",
        "unsere",
    ]
)

SENTENCE_END = re.compile(r"[.!?…]+[\"'“”»«)\]]*(?=\s|$)")
PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n+")
LIST_OR_HEADING_LINE = re.compile(r"\n(?=[ \t]*(?:[-*•+]\s|\d{1,3}[.)]\s|#{1,6}\s))")
HEADING = re.compile(r"\s*#{1,6}\s")

FENCED_CODE = re.compile(r"^[ \t]*(```|~~~).*?^[ \t]*\1[^\n]*$", re.MULTILINE | re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]+`")
URL = re.compile(r"(?:https?://|www\.)\S+?(?=[.,;:!?)\]]*(?:\s|$))")


@dataclass
class Sentence:
    start: int
    end: int
    paragraph: int
    words: int


def blank(match: re.Match[str]) -> str:
    """Replace a span with spaces of the same length, keeping newlines and offsets."""
    return re.sub(r"[^\n]", " ", match.group(0))


def mask(text: str) -> tuple[str, dict[str, int]]:
    """Blank out code and URLs so they count as neither words nor sentence ends."""
    counts = {}
    for name, pattern in (
        ("code_blocks", FENCED_CODE),
        ("inline_code", INLINE_CODE),
        ("urls", URL),
    ):
        text, counts[name] = pattern.subn(blank, text)
    return text, counts


def spans(text: str, splitter: re.Pattern[str], start: int, end: int) -> list[tuple[int, int]]:
    """Split text[start:end] at splitter matches; return non-blank (start, end) spans."""
    out, cursor = [], start
    for match in splitter.finditer(text, start, end):
        out.append((cursor, match.start()))
        cursor = match.end()
    out.append((cursor, end))
    return [(a, b) for a, b in out if text[a:b].strip()]


LOOKBACK = 40  # chars before a period inspected for an abbreviation or ordinal
NEXT_WORD = re.compile(r"\s*(\S+)")
OPENING_PUNCT = "([\"'„“»«"


def is_boundary(text: str, block_start: int, match: re.Match[str], block_end: int) -> bool:
    """Decide whether a period/!/? at `match` ends a sentence."""
    following = NEXT_WORD.match(text, match.end(), block_end)
    if following is None:
        return True
    next_word = following.group(1)
    if next_word[0].islower():
        return False
    if not match.group(0).startswith("."):
        return True
    window_start = max(block_start, match.start() - LOOKBACK)
    before = text[window_start : match.start() + 1].split()
    if window_start > block_start and len(before) > 2:
        before = before[1:]  # the first token may be cut off by the window
    if not before:
        return True
    token = before[-1].lstrip(OPENING_PUNCT).lower()
    joined = (before[-2] + before[-1]).lstrip(OPENING_PUNCT).lower() if len(before) > 1 else ""
    if token in SENTENCE_FINAL_ABBREVIATIONS or joined in SENTENCE_FINAL_ABBREVIATIONS:
        return True  # "usw." before a capital usually closes the sentence
    if token in ABBREVIATIONS or joined in ABBREVIATIONS:
        return False
    if re.fullmatch(rf"[{LETTER}]\.", token):  # initials, "S. 12", the "B." of "z. B."
        return False
    if re.fullmatch(r"\d{1,4}\.", token):
        previous = before[-2].lower() if len(before) > 1 else ""
        if next_word.strip(",.;:").lower() in MONTHS or previous in ORDINAL_CONTEXT:
            return False
    return True


def split_sentences(text: str) -> tuple[list[Sentence], int, int]:
    """Return (sentences, paragraph count, heading count) for already-masked text."""
    sentences: list[Sentence] = []
    headings = 0
    paragraphs = spans(text, PARAGRAPH_BREAK, 0, len(text))
    for p_index, (p_start, p_end) in enumerate(paragraphs, start=1):
        for b_start, b_end in spans(text, LIST_OR_HEADING_LINE, p_start, p_end):
            if HEADING.match(text, b_start):
                headings += 1
                continue
            cursor = b_start
            for match in SENTENCE_END.finditer(text, b_start, b_end):
                if is_boundary(text, b_start, match, b_end):
                    _append(sentences, text, cursor, match.end(), p_index)
                    cursor = match.end()
            _append(sentences, text, cursor, b_end, p_index)
    return sentences, len(paragraphs), headings


def _append(sentences: list[Sentence], text: str, start: int, end: int, paragraph: int) -> None:
    words = len(WORD.findall(text, start, end))
    if words:
        sentences.append(Sentence(start, end, paragraph, words))
