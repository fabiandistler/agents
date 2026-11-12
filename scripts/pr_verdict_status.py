"""Plan the `pr-review/verdict` commit status for one reviewed head.

The status lets the ruleset make a merge wait for the review without making
the review a gate: any verdict turns it green, whatever it says (ADR-0011
decision A, amended 2026-11-11). It is set on the head SHA the plan assessed,
so a new push starts with no status on the new head, which a required check
reads as "Waiting for status to be reported". The planner is model-free and
never writes; ``pr_actions.py`` resolves the action and ``pr_apply.py`` sends it.
"""

from __future__ import annotations

# The context the ruleset requires; the writer refuses any other, so the
# publish job's statuses scope can never touch `checks` or another check.
CONTEXT = "pr-review/verdict"
# The states this pipeline sets. `failure` is never used: the review is
# advisory, so no verdict may read as a failed check.
STATES = ("success", "pending", "error")
# One short line, so the merge box shows it whole.
MAX_DESCRIPTION = 140

UNAVAILABLE = "No verdict: the review was unavailable. Re-run pr-review for this head."
DRAFT = "Draft: the review runs when the pull request is marked ready."
FORK = "Fork: never reviewed by the model; the maintainer reviews it."


def _verdict_description(review: dict) -> str:
    partial = " (partial review)" if review.get("partial") is True else ""
    return f"Verdict: {review['verdict']}{partial}. Advisory; read the review comment."


def status_for(context: dict, review: dict) -> tuple[str, str]:
    """Return the state and description for the head the review covered.

    Any verdict is green. An unavailable review is an error: nothing will
    follow on its own, so it waits for a re-run. A draft stays pending until
    the ``ready_for_review`` run reviews it. A fork is never reviewed by the
    model, so its skipped review is final and green; a push to it starts a
    new head without a status.
    """
    if review["status"] == "ok":
        return "success", _verdict_description(review)
    if review["status"] == "unavailable":
        return "error", UNAVAILABLE
    if context.get("fork") is True and context.get("draft") is not True:
        return "success", FORK
    return "pending", DRAFT


def status_action(context: dict, review: dict, target_url: str | None = None) -> dict:
    """Return the ``set_status`` action pinned to the context's head SHA."""
    state, description = status_for(context, review)
    return {
        "kind": "set_status",
        "sha": context["head_sha"],
        "context": CONTEXT,
        "state": state,
        "description": description,
        "target_url": target_url,
    }
