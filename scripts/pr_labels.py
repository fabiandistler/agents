"""The labels the PR review pipeline reads and writes.

Every label name the planner, the auto-merge decision and the writer use is
defined here once, with the colour and description the writer creates it with.
"""

from __future__ import annotations

RISK_PREFIX = "risk:"
VERDICT_PREFIX = "review:"
NEEDS_REVIEW = "needs-review"
# The hard veto: it disables any auto-merge, whoever enabled it (decision B).
DO_NOT_MERGE = "do-not-merge"
# Marks an auto-merge the bot enabled itself; one without it belongs to a human.
AUTO_MERGE_BOT = "auto-merge:bot"

# The ten labels with their colour and description. Creating them is
# idempotent, so a fresh repository needs no manual setup before the first
# publish run.
LABELS = {
    f"{RISK_PREFIX}low": ("0e8a16", "Low risk: documentation or reports, auto-merge eligible"),
    f"{RISK_PREFIX}medium": ("fbca04", "Medium risk: needs a human review"),
    f"{RISK_PREFIX}high": ("b60205", "High risk: never auto-merged"),
    f"{VERDICT_PREFIX}pass": ("0e8a16", "Review verdict: pass"),
    f"{VERDICT_PREFIX}concerns": ("fbca04", "Review verdict: concerns"),
    f"{VERDICT_PREFIX}block": ("b60205", "Review verdict: block"),
    f"{VERDICT_PREFIX}unavailable": ("6a737d", "The review could not be produced"),
    NEEDS_REVIEW: ("d93f0b", "A human should review this pull request"),
    DO_NOT_MERGE: ("000000", "Hard stop: never merge this pull request"),
    AUTO_MERGE_BOT: ("1d76db", "Auto-merge enabled by the review bot"),
}
