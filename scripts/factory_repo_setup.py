#!/usr/bin/env python3
"""What scripts/factory-repo-setup.sh sets up in a target repository.

The wizard holds the dialogue and the gh calls; this module holds the
factory's side of it: the labels a target needs and the patterns its Actions
allow-list must hold. Standard library only.

    factory_repo_setup.py labels             # the labels, one per line
    factory_repo_setup.py missing-patterns   # stdin: selected-actions JSON
    factory_repo_setup.py allowlist-body     # stdin: selected-actions JSON

``missing-patterns`` prints the factory patterns the list lacks, one per line;
``allowlist-body`` prints the JSON for
``PUT repos/{owner}/{repo}/actions/permissions/selected-actions`` that adds
them. That PUT sets the list as a whole, so the body carries the current
patterns and flags too. Exit 0 ok, 2 usage error.
"""

from __future__ import annotations

import json
import sys
from typing import TextIO

from issue_triage_policy import CATEGORIES, STATE_LABELS

# The factory's reusable workflows and the actions they run
# (docs/agents/factory-onboarding.md, "Manual steps"; pr-review-runbook.md,
# "Actions policy").
FACTORY_PATTERNS = (
    "fabiandistler/agents/.github/workflows/*",
    "actions/checkout@*",
    "actions/setup-python@*",
    "actions/upload-artifact@*",
    "actions/download-artifact@*",
    "anthropics/claude-code-action@*",
)

USAGE = "usage: factory_repo_setup.py {labels|missing-patterns|allowlist-body}\n"


def required_labels() -> tuple[str, ...]:
    """The state labels of the triage, then the issue categories."""
    return STATE_LABELS + CATEGORIES


def missing_patterns(selected: dict) -> list[str]:
    """The factory patterns a selected-actions response does not allow yet."""
    allowed = selected.get("patterns_allowed") or []
    return [pattern for pattern in FACTORY_PATTERNS if pattern not in allowed]


def allowlist_body(selected: dict) -> dict:
    """The selected-actions PUT body: current patterns and flags, plus the missing."""
    patterns = list(selected.get("patterns_allowed") or [])
    return {
        "github_owned_allowed": bool(selected.get("github_owned_allowed")),
        "verified_allowed": bool(selected.get("verified_allowed")),
        "patterns_allowed": patterns + missing_patterns(selected),
    }


def main(argv: list[str] | None = None, stdin: TextIO | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["labels"]:
        print("\n".join(required_labels()))
        return 0
    if args in (["missing-patterns"], ["allowlist-body"]):
        selected = json.load(stdin or sys.stdin)
        if args[0] == "missing-patterns":
            print("\n".join(missing_patterns(selected)))
        else:
            print(json.dumps(allowlist_body(selected)))
        return 0
    sys.stderr.write(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main())
