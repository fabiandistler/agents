"""Load the curated marker lists in ../assets/marker_lists.json.

Each category becomes one compiled, case-insensitive pattern with its evidence
tier; the file's 'format' key documents the entry syntax `phrase_pattern`
implements. A missing or malformed file raises `MarkerListError`.
Stdlib only; Python 3.11+.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from german_sentences import LETTER

TIERS = ("strong", "medium", "weak")


class MarkerListError(ValueError):
    """assets/marker_lists.json is missing, unreadable or malformed."""


@dataclass
class Category:
    name: str
    tier: str
    pattern: re.Pattern[str]
    hits: list[tuple[int, int]] = field(default_factory=list)


def phrase_pattern(entry: str) -> str:
    """Turn one list entry into a regex fragment (see the file's 'format' key)."""
    if entry.startswith("re:"):
        return entry[3:]
    prefix = suffix = ""
    if entry.startswith("*"):
        prefix, entry = rf"[{LETTER}]*", entry[1:]
    if entry.endswith("*"):
        suffix, entry = rf"[{LETTER}]*", entry[:-1]
    body = r"\s+".join(re.escape(part) for part in entry.split())
    return rf"(?<![{LETTER}0-9]){prefix}{body}{suffix}(?![{LETTER}0-9])"


def load_markers(path: Path) -> dict:
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MarkerListError(f"cannot read {path.name}: {exc}") from exc
    categories = spec.get("kategorien")
    if not isinstance(categories, dict) or not categories:
        raise MarkerListError(f"{path.name}: 'kategorien' must be a non-empty object")
    compiled = []
    for name, body in categories.items():
        entries = body.get("eintraege") if isinstance(body, dict) else None
        tier = body.get("stufe") if isinstance(body, dict) else None
        if tier not in TIERS:
            raise MarkerListError(f"{path.name}: category '{name}' needs 'stufe' in {TIERS}")
        if not isinstance(entries, list) or not all(isinstance(e, str) and e for e in entries):
            raise MarkerListError(f"{path.name}: category '{name}' needs a list of strings")
        # Longest entry first, so "es ist wichtig zu beachten" wins over "es ist wichtig".
        ordered = sorted(entries, key=len, reverse=True)
        try:
            pattern = re.compile(
                "|".join(f"(?:{phrase_pattern(e)})" for e in ordered), re.IGNORECASE
            )
        except re.error as exc:
            raise MarkerListError(f"{path.name}: category '{name}' has a bad regex: {exc}") from exc
        compiled.append(Category(name, tier, pattern))
    suffixes: list[str] = []
    pronouns: list[str] = []
    for key, target in (("nominal_suffixe", suffixes), ("ich_wir", pronouns)):
        value = spec.get(key)
        if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
            raise MarkerListError(f"{path.name}: '{key}' must be a list of strings")
        target.extend(str(v) for v in value)
    return {
        "categories": compiled,
        "nominal": re.compile(
            rf"(?<![{LETTER}])[A-ZÄÖÜ][{LETTER}]{{3,}}(?:{'|'.join(map(re.escape, suffixes))})"
            rf"(?![{LETTER}])"
        ),
        "first_person": re.compile(
            "|".join(f"(?:{phrase_pattern(p)})" for p in pronouns), re.IGNORECASE
        ),
        "stand": spec.get("stand"),
        "naechste_pruefung": spec.get("naechste_pruefung"),
    }
