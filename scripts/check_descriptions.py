#!/usr/bin/env python3
"""Enforce the skill-description budget.

Run from repo root:
    python3 scripts/check_descriptions.py    # exit 1 on any over-budget skill

Codex CLI budgets only ~2% of the context window for skill descriptions, so an
oversized frontmatter `description` gets the list truncated — the metadata that
drives triggering is exactly what gets cut. This check keeps each SKILL.md
`description` within a hard budget and the aggregate over auto-triggered skills
under the Codex cap. Trigger lists and feature enumerations belong in the
SKILL.md body (progressive disclosure), not the always-loaded frontmatter.

This is a stricter *policy* layer on top of build_manifest.py's 1024-char
spec cap; the two are deliberately decoupled. Stdlib-only; reuses the
frontmatter parser from build_manifest.py.
"""

from __future__ import annotations

import sys

from build_manifest import (
    extract_frontmatter,
    find_skill_files,
    parse_frontmatter,
)

# Per-skill budgets, in characters.
DEFAULT_BUDGET = 250
ALLOWLIST_BUDGET = 400
# High-traffic skills allowed the wider budget. Keep this list short.
ALLOWLIST = frozenset({"architecture-pattern-advisor", "tdd"})

# Total description size across auto-triggered skills must stay under the Codex
# ~2% cap (~5,400 tokens at ~270k context); ~10,000 chars ≈ ~2,500 tokens.
AUTO_TOTAL_BUDGET = 10_000


def budget_for(name: str) -> int:
    return ALLOWLIST_BUDGET if name in ALLOWLIST else DEFAULT_BUDGET


def main() -> int:
    errors: list[str] = []
    auto_total = 0

    for skill_md in find_skill_files():
        text = skill_md.read_text(encoding="utf-8")
        fm = parse_frontmatter(extract_frontmatter(text))
        name = fm.get("name") or skill_md.parent.name
        description = fm.get("description")
        if not isinstance(description, str) or not description:
            errors.append(f"{name}: missing or empty 'description'")
            continue
        activation = fm.get("activation", "auto")
        length = len(description)
        budget = budget_for(name)
        if length > budget:
            errors.append(
                f"{name}: description is {length} chars (budget {budget})."
                " Move trigger detail into the SKILL.md body (## When to use)."
            )
        if activation == "auto":
            auto_total += length

    if auto_total > AUTO_TOTAL_BUDGET:
        errors.append(
            f"aggregate auto-skill description size is {auto_total} chars"
            f" (budget {AUTO_TOTAL_BUDGET}); trim the longest descriptions"
            " or mark user-invoked skills 'activation: command'."
        )

    if errors:
        sys.stderr.write("description budget exceeded:\n")
        for e in errors:
            sys.stderr.write(f"  - {e}\n")
        return 1

    print(
        f"descriptions within budget (auto total {auto_total}/{AUTO_TOTAL_BUDGET} chars)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
