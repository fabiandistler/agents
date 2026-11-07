#!/usr/bin/env python3
"""Count style signals in a German text; the numbers behind a KI-Stil check.

The script measures, it does not judge. It never says whether a person or a
model wrote the text: detectors and checklists cannot decide that. It reports
where wording reads generic, and how dense that wording is, so the agent can
weigh the signals by genre and evidence tier.

What it counts:

  * Sentence lengths in words: mean, SD, CV (SD / mean), median, min, max,
    and the share of sentences under 8 and over 30 words. Low dispersion is
    the signal; there is no "right" length band.
  * Hits from the curated lists in ../assets/marker_lists.json (floskeln,
    lehrbuchvokabular, abstrakte_substantive, signifikanz, lehnmuster), each
    with its evidence tier, hits per 100 words, and match positions
    (sentence, paragraph, character offset). The text itself is not echoed.
  * Nominal style: capitalised words ending in a nominal suffix, per 100 words.
  * Figure candidates: triads ("A, B und C"), "nicht X, sondern Y",
    "nicht nur ... sondern auch". Candidates only; a regex cannot tell a
    deliberate figure from a reflex.
  * Repeated paragraph and sentence openings.
  * Dashes: a spaced en dash " – " is standard German and not a signal; an
    unspaced em dash "—" is English typography, a weak hint at most.
  * Clusters: windows of 3 consecutive sentences with 3+ hits from 2+
    categories. Clusters matter; single hits do not.
  * Own-substance hints: digit tokens and first-person pronouns. Their absence
    is a question for the reader, not evidence.

Fenced code, inline code, URLs and Markdown headings are masked out before
counting, so PR descriptions and ADRs can be scanned as they are.

Plain language and non-native writing are protected by design: short
sentences, simple words and few connectors raise no counter here, and lexical
variety is deliberately not measured (low variety is what makes detectors
flag non-native writers, Liang et al. 2023).

Stdlib only; Python 3.11+.
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import statistics
import sys
from pathlib import Path

from german_sentences import LETTER, WORD, Sentence, mask, split_sentences
from marker_lists import TIERS, MarkerListError, load_markers

MARKER_FILE = Path(__file__).resolve().parent.parent / "assets" / "marker_lists.json"
SHORT_TEXT_WORDS = 80
MIN_SENTENCES_FOR_DISPERSION = 5
SHORT_SENTENCE = 8
LONG_SENTENCE = 30
CLUSTER_WINDOW = 3
CLUSTER_MIN_HITS = 3
CLUSTER_MIN_CATEGORIES = 2

EXIT_OK, EXIT_IO, EXIT_USAGE, EXIT_EMPTY, EXIT_MARKERS = 0, 1, 2, 3, 4

DASH = re.compile("[–—-]")

TRIAD = re.compile(
    rf"\b[{LETTER}][{LETTER}-]*(?:\s[{LETTER}][{LETTER}-]*)?,\s+"
    rf"[{LETTER}][{LETTER}-]*(?:\s[{LETTER}][{LETTER}-]*)?,?\s+"
    rf"(?:und|oder|sowie)\s+[{LETTER}][{LETTER}-]*"
)
NOT_ONLY_BUT_ALSO = re.compile(r"\bnicht\s+nur\b[^.!?]{0,160}?\bsondern\s+auch\b", re.IGNORECASE)
NOT_X_BUT_Y = re.compile(
    r"\b(?:nicht|kein(?:e|en|em|er|es)?)\b(?!\s+nur\b)[^.!?]{0,120}?,?\s+sondern\b(?!\s+auch\b)",
    re.IGNORECASE,
)
# "Es geht nicht um X. Es geht um Y." / "Nicht X. Sondern Y." across a sentence break.
NOT_X_BUT_Y_SPLIT = re.compile(
    r"\b(?:es\s+geht\s+nicht\s+um|nicht)\b[^.!?]{1,100}[.!?]\s+(?:es\s+geht\s+um|sondern)\b",
    re.IGNORECASE,
)
# "Wir bauen keine Software. Wir bauen Vertrauen." -- the same two words reopen the next sentence.
NOT_X_BUT_Y_PARALLEL = re.compile(
    rf"\b([{LETTER}]+\s+[{LETTER}]+)\s+(?:nicht|kein(?:e|en|em|er|es)?)\b[^.!?]{{1,100}}[.!?]\s+\1\b",
    re.IGNORECASE,
)
# A sentence made of three bare items: "Schnell, sicher, skalierbar."
TRIAD_FRAGMENT = re.compile(
    rf"(?:^|(?<=[.!?:]\s))[{LETTER}]+,\s+[{LETTER}]+,\s+[{LETTER}]+[.!?]", re.MULTILINE
)

USAGE_EPILOG = """examples:
  python3 scripts/style_scan.py draft.md
  python3 scripts/style_scan.py - --max-positions 0 --output scan.json < draft.md

exit codes: 0 ok | 1 cannot read input or write output | 2 bad usage
            3 input contains no words | 4 marker list missing or malformed"""


def without_overlaps(hits) -> list[tuple[int, int]]:
    """Sort (start, end) spans and keep only those not overlapping an earlier kept span."""
    kept: list[tuple[int, int]] = []
    for start, end in sorted(set(hits)):
        if not kept or start >= kept[-1][1]:
            kept.append((start, end))
    return kept


def length_stats(sentences: list[Sentence]) -> dict:
    lengths = [s.words for s in sentences]
    mean = statistics.fmean(lengths)
    sd = statistics.stdev(lengths) if len(lengths) > 1 else None
    return {
        "n": len(lengths),
        "mean": round(mean, 2),
        "sd": round(sd, 2) if sd is not None else None,
        "cv": round(sd / mean, 3) if sd is not None and mean else None,
        "median": statistics.median(lengths),
        "min": min(lengths),
        "max": max(lengths),
        "share_under_8": round(sum(n < SHORT_SENTENCE for n in lengths) / len(lengths), 3),
        "share_over_30": round(sum(n > LONG_SENTENCE for n in lengths) / len(lengths), 3),
    }


def locate(sentences: list[Sentence], starts: list[int], offset: int) -> int | None:
    """Index of the sentence containing `offset`, or None (masked or between sentences).

    `starts` is [s.start for s in sentences], built once by the caller.
    """
    index = bisect.bisect_right(starts, offset) - 1
    if index >= 0 and offset < sentences[index].end:
        return index
    return None


def per_100(count: int, words: int) -> float:
    return round(100 * count / words, 2) if words else 0.0


def positions(text, sentences, hits, limit) -> tuple[list[dict], bool]:
    shown = hits if limit == 0 else hits[:limit]
    starts = [s.start for s in sentences]
    out = []
    for start, end in shown:
        index = locate(sentences, starts, start)
        out.append(
            {
                "match": " ".join(text[start:end].split()),
                "sentence": index + 1 if index is not None else None,
                "paragraph": sentences[index].paragraph if index is not None else None,
                "offset": start,
            }
        )
    return out, len(shown) < len(hits)


def classify_dashes(text: str) -> dict[str, list[int]]:
    """Offsets of each dash kind. List markers at line start are not dashes."""
    kinds: dict[str, list[int]] = {
        "spaced_en_dash": [],
        "unspaced_en_dash": [],
        "number_range": [],
        "spaced_em_dash": [],
        "unspaced_em_dash": [],
        "spaced_hyphen": [],
    }
    for found in DASH.finditer(text):
        i, char = found.start(), found.group(0)
        left = text[i - 1] if i > 0 else "\n"
        right = text[i + 1] if i + 1 < len(text) else "\n"
        j = i - 1
        while j >= 0 and text[j] in " \t":
            j -= 1
        line_start = j < 0 or text[j] == "\n"
        spaced = left.isspace() and right.isspace()
        if char == "-":
            if spaced and not line_start:
                kinds["spaced_hyphen"].append(i)
        elif char == "–":
            if line_start:
                continue
            around = text[max(0, i - 2) : i + 3].replace(" ", "")
            if re.search(r"\d–\d", around):
                kinds["number_range"].append(i)
            elif spaced:
                kinds["spaced_en_dash"].append(i)
            else:
                kinds["unspaced_en_dash"].append(i)
        elif not line_start:
            kinds["spaced_em_dash" if spaced else "unspaced_em_dash"].append(i)
    return kinds


def openings(text: str, sentences: list[Sentence]) -> dict:
    """Repeated first words of paragraphs and sentences."""
    by_paragraph: dict[int, Sentence] = {}
    for sentence in sentences:
        by_paragraph.setdefault(sentence.paragraph, sentence)

    def first_words(sentence: Sentence, n: int) -> str:
        return " ".join(w.lower() for w in WORD.findall(text, sentence.start, sentence.end)[:n])

    paragraph_repeats: list[tuple[str, list[int]]] = []
    for n, minimum in ((2, 2), (1, 3)):
        groups: dict[str, list[int]] = {}
        for p_index, sentence in by_paragraph.items():
            groups.setdefault(first_words(sentence, n), []).append(p_index)
        covered = {opening.split()[0] for opening, _ in paragraph_repeats}
        for opening, paragraphs in groups.items():
            if len(paragraphs) >= minimum and opening and opening.split()[0] not in covered:
                paragraph_repeats.append((opening, paragraphs))
    starters: dict[str, int] = {}
    for sentence in sentences:
        word = first_words(sentence, 1)
        starters[word] = starters.get(word, 0) + 1
    sentence_repeats = [
        {"word": word, "count": count, "share": round(count / len(sentences), 3)}
        for word, count in sorted(starters.items(), key=lambda kv: -kv[1])
        if count >= 3 and count / len(sentences) >= 0.25
    ][:3]
    return {
        "paragraph_repeats": [
            {"opening": opening, "paragraphs": paragraphs}
            for opening, paragraphs in paragraph_repeats[:5]
        ],
        "sentence_repeats": sentence_repeats,
    }


def clusters(sentences: list[Sentence], tagged_hits: list[tuple[int, str]]) -> list[dict]:
    """Merge windows of CLUSTER_WINDOW sentences that pass the hit/category thresholds."""
    per_sentence: list[list[str]] = [[] for _ in sentences]
    starts = [s.start for s in sentences]
    for offset, category in tagged_hits:
        index = locate(sentences, starts, offset)
        if index is not None:
            per_sentence[index].append(category)
    windows = []
    for i in range(max(1, len(sentences) - CLUSTER_WINDOW + 1)):
        cats = [c for bucket in per_sentence[i : i + CLUSTER_WINDOW] for c in bucket]
        if len(cats) >= CLUSTER_MIN_HITS and len(set(cats)) >= CLUSTER_MIN_CATEGORIES:
            windows.append((i, min(i + CLUSTER_WINDOW, len(sentences)) - 1))
    merged: list[list[int]] = []
    for first, last in windows:
        if merged and first <= merged[-1][1]:
            merged[-1][1] = last
        else:
            merged.append([first, last])
    out = []
    for first, last in merged:
        cats = [c for bucket in per_sentence[first : last + 1] for c in bucket]
        out.append(
            {
                "sentences": [first + 1, last + 1],
                "paragraph": sentences[first].paragraph,
                "hits": len(cats),
                "categories": sorted(set(cats)),
            }
        )
    return out


def scan(raw: str, markers: dict, max_positions: int) -> dict:
    text, masked = mask(raw)
    sentences, paragraph_count, headings = split_sentences(text)
    words = sum(s.words for s in sentences)
    if not words:
        raise ValueError("no words")
    short = words < SHORT_TEXT_WORDS
    notes = []
    if short:
        notes.append(
            f"Unter {SHORT_TEXT_WORDS} Wörtern: Dichte- und Streuungswerte sind nicht "
            "belastbar, nur reduzierte Prüfung."
        )
    elif len(sentences) < MIN_SENTENCES_FOR_DISPERSION:
        notes.append("Weniger als 5 Sätze: Satzlängen-Streuung nicht belastbar.")

    tagged: list[tuple[int, str]] = []
    tier_totals = {tier: 0 for tier in TIERS}
    lexical = {}
    for category in markers["categories"]:
        hits = [(m.start(), m.end()) for m in category.pattern.finditer(text)]
        tagged += [(start, category.name) for start, _ in hits]
        tier_totals[category.tier] += len(hits)
        shown, truncated = positions(text, sentences, hits, max_positions)
        lexical[category.name] = {
            "tier": category.tier,
            "hits": len(hits),
            "per_100_words": per_100(len(hits), words),
            "positions": shown,
            "truncated": truncated,
        }

    figure_patterns = {
        "triad": ("medium", [TRIAD, TRIAD_FRAGMENT]),
        "nicht_x_sondern_y": ("medium", [NOT_X_BUT_Y, NOT_X_BUT_Y_SPLIT, NOT_X_BUT_Y_PARALLEL]),
        "nicht_nur_sondern_auch": ("medium", [NOT_ONLY_BUT_ALSO]),
    }
    figures = {}
    for name, (tier, patterns) in figure_patterns.items():
        hits = without_overlaps((m.start(), m.end()) for p in patterns for m in p.finditer(text))
        tagged += [(start, name) for start, _ in hits]
        tier_totals[tier] += len(hits)
        shown, truncated = positions(text, sentences, hits, max_positions)
        figures[name] = {
            "tier": tier,
            "candidates": len(hits),
            "per_100_words": per_100(len(hits), words),
            "positions": shown,
            "truncated": truncated,
        }

    nominal_words = [m.group(0) for m in markers["nominal"].finditer(text)]
    nominal_top: dict[str, int] = {}
    for word in nominal_words:
        nominal_top[word] = nominal_top.get(word, 0) + 1

    dashes = classify_dashes(text)
    em_shown, em_truncated = positions(
        text, sentences, [(i, i + 1) for i in dashes["unspaced_em_dash"]], max_positions
    )
    all_clusters = clusters(sentences, tagged)
    tier_totals["strong"] += len(nominal_words)
    tier_totals["weak"] += len(dashes["unspaced_em_dash"])

    return {
        "marker_lists": {
            "source": "eigene Beobachtung, keine Studie",
            "stand": markers["stand"],
            "naechste_pruefung": markers["naechste_pruefung"],
        },
        "text": {
            "words": words,
            "sentences": len(sentences),
            "paragraphs": paragraph_count,
            "headings_skipped": headings,
            "masked": masked,
        },
        "short_text": short,
        "dispersion_reliable": not short and len(sentences) >= MIN_SENTENCES_FOR_DISPERSION,
        "notes": notes,
        "sentence_length": length_stats(sentences),
        "lexical": lexical,
        "nominal_style": {
            "tier": "strong",
            "count": len(nominal_words),
            "per_100_words": per_100(len(nominal_words), words),
            "top": sorted(nominal_top.items(), key=lambda kv: (-kv[1], kv[0]))[:10],
        },
        "figures": figures,
        "openings": openings(text, sentences),
        "dashes": {
            "tier": "weak",
            "counts": {kind: len(offsets) for kind, offsets in dashes.items()},
            "unspaced_em_per_100_words": per_100(len(dashes["unspaced_em_dash"]), words),
            "unspaced_em_positions": em_shown,
            "truncated": em_truncated,
        },
        "clusters": all_clusters[:10],
        "clusters_total": len(all_clusters),
        "tier_hits_per_100_words": {t: per_100(n, words) for t, n in tier_totals.items()},
        "substance_hints": {
            "digit_tokens": len(re.findall(r"(?<!\w)\d[\d.,%]*", text)),
            "first_person": len(markers["first_person"].findall(text)),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="style_scan.py",
        description="Count style signals in a German text; JSON to stdout. Measures, never judges.",
        epilog=USAGE_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("path", nargs="?", help="text file, or '-' for stdin (default: stdin)")
    parser.add_argument(
        "--max-positions",
        type=int,
        default=10,
        metavar="N",
        help="positions listed per category, 0 = all (default: 10)",
    )
    parser.add_argument("--output", metavar="FILE", help="write the JSON to FILE instead")
    return parser


def read_input(path: str | None) -> str:
    if path in (None, "-"):
        return sys.stdin.buffer.read().decode("utf-8-sig")
    return Path(path).read_bytes().decode("utf-8-sig")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_positions < 0:
        sys.stderr.write("error: --max-positions must be 0 or greater\n")
        return EXIT_USAGE
    if args.path is None and sys.stdin.isatty():
        sys.stderr.write("error: pass a file path, or pipe the text on stdin with '-'\n")
        return EXIT_USAGE
    try:
        markers = load_markers(MARKER_FILE)
    except MarkerListError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return EXIT_MARKERS
    try:
        raw = read_input(args.path)
    except (OSError, UnicodeDecodeError) as exc:
        sys.stderr.write(f"error: cannot read input as UTF-8 text: {exc}\n")
        return EXIT_IO
    try:
        report = scan(raw, markers, args.max_positions)
    except ValueError:
        sys.stderr.write("error: the input contains no words to scan\n")
        return EXIT_EMPTY
    payload = json.dumps(report, ensure_ascii=False, indent=1)
    if args.output is None:
        print(payload)
        return EXIT_OK
    try:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"error: cannot write {args.output}: {exc}\n")
        return EXIT_IO
    sys.stderr.write(f"wrote {args.output}\n")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
