#!/usr/bin/env python3
"""Report per-skill eval-prompt coverage (warn-only until content lands).

Run from repo root:
    python3 scripts/check_evals.py            # warn on gaps, exit 0
    python3 scripts/check_evals.py --strict   # exit 1 on any gap

Every auto/router skill ships skills/<name>/evals.json (ADR-0006) with at
least three should_trigger prompts, at least one should_not_trigger prompt,
and an optional expected_behavior string. Command skills are exempt. The
default run is warn-only so CI never breaks on main while no skill ships
evals yet; CI flips to --strict once content lands. Stdlib-only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from catalogue import load_catalogue

REPO_ROOT = Path(__file__).resolve().parent.parent
MIN_POSITIVE = 3
MIN_NEGATIVE = 1
KNOWN_KEYS = frozenset({"should_trigger", "should_not_trigger", "expected_behavior"})

USAGE = """usage: check_evals.py [--strict] [--help]

Check that every auto/router skill ships skills/<name>/evals.json
with >=3 should_trigger and >=1 should_not_trigger prompts (ADR-0006).

  --strict   exit 1 on any gap (CI flips to this once content lands)
  --help     show this message
"""


def eval_path(name: str) -> Path:
    """Filesystem location of a skill's eval prompts."""
    return REPO_ROOT / "skills" / name / "evals.json"


def check_list(data: dict, key: str, minimum: int, path: Path) -> list[str]:
    """Validate one prompt list holds enough non-empty strings."""
    value = data.get(key)
    if not isinstance(value, list):
        return [f"{path}: '{key}' must be a list of >= {minimum} non-empty strings"]
    items = [v for v in value if isinstance(v, str) and v.strip()]
    if len(items) < minimum:
        return [f"{path}: '{key}' has {len(items)} usable prompt(s), need >= {minimum}"]
    return []


def check_file(path: Path) -> list[str]:
    """Validate one evals.json against the ADR-0006 schema."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return [f"{path}: unreadable: {exc}"]
    except json.JSONDecodeError as exc:
        return [f"{path}: invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return [f"{path}: top level must be an object"]
    errors: list[str] = []
    errors += check_list(data, "should_trigger", MIN_POSITIVE, path)
    errors += check_list(data, "should_not_trigger", MIN_NEGATIVE, path)
    expected = data.get("expected_behavior")
    if expected is not None and (not isinstance(expected, str) or not expected.strip()):
        errors.append(f"{path}: 'expected_behavior' must be a non-empty string")
    unknown = sorted(set(data) - KNOWN_KEYS)
    if unknown:
        errors.append(f"{path}: unknown key(s): {', '.join(unknown)}")
    return errors


def collect_gaps() -> tuple[list[str], int, int]:
    """Return (gap messages, skills covered, auto/router skills checked)."""
    gaps: list[str] = []
    covered = 0
    checked = 0
    for entry in load_catalogue():
        if entry.activation not in ("auto", "router"):
            continue
        checked += 1
        path = eval_path(entry.name)
        if not path.is_file():
            gaps.append(f"{entry.name}: missing skills/{entry.name}/evals.json")
            continue
        file_errors = check_file(path)
        if file_errors:
            gaps.extend(file_errors)
            continue
        covered += 1
    return gaps, covered, checked


def main(argv: list[str] | None = None) -> int:
    """Run the coverage check; warn-only unless --strict is passed."""
    args = sys.argv[1:] if argv is None else argv
    if "--help" in args or "-h" in args:
        sys.stdout.write(USAGE)
        return 0
    strict = "--strict" in args
    gaps, covered, checked = collect_gaps()
    if strict and gaps:
        sys.stderr.write(f"evals coverage: {covered}/{checked} auto+router skills\n")
        for gap in gaps:
            sys.stderr.write(f"  - {gap}\n")
        return 1
    sys.stdout.write(f"evals coverage: {covered}/{checked} auto+router skills (warn-only)\n")
    for gap in gaps:
        sys.stdout.write(f"  warn: {gap}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
