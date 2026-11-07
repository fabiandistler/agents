"""Render the publish step summary of the PR review workflow.

``pr_publish.py --summary FILE`` appends this Markdown to the run page: the
decision, what the review covered, and the labels. A dry run lists the labels
it planned; a write lists only the labels it actually wrote, which a failed
write leaves short of the plan. The full JSON follows for the details.
"""

from __future__ import annotations

import json

# The review artifact carries no confidence value. What it does say about how
# far to trust the verdict is whether the model saw the whole diff.
COVERAGE = {
    "unavailable": "none, the review is unavailable",
    "skipped": "none, the review was skipped",
}


def _confidence(review: dict) -> str:
    status = review.get("status")
    if status in COVERAGE:
        return COVERAGE[status]
    if review.get("partial") is True:
        return "partial review, the input was truncated"
    return "full review of the diff"


def _labels(added: list[str], removed: list[str]) -> str:
    changes = [f"+{label}" for label in added] + [f"-{label}" for label in removed]
    return ", ".join(changes) or "none"


def _planned_labels(plan: dict) -> tuple[list[str], list[str]]:
    added: list[str] = []
    removed: list[str] = []
    for action in plan.get("actions", []):
        if action.get("kind") == "set_labels":
            added += action.get("add", [])
            removed += action.get("remove", [])
    return added, removed


def _written_labels(results: list[dict]) -> tuple[list[str], list[str]]:
    added: list[str] = []
    removed: list[str] = []
    for result in results:
        added += result.get("added", [])
        removed += result.get("removed", [])
    return added, removed


def _action_lines(results: list[dict]) -> list[str]:
    return [
        f"- {result['kind']}: {'ok' if result['ok'] else 'failed'}, {result['detail']}"
        for result in results
    ]


def render_summary(payload: dict, review: dict) -> str:
    """Return the Markdown summary of a plan or of a write's results wrapper."""
    follow_up = payload.get("follow_up") or {}
    plan = follow_up.get("plan") or payload.get("plan", payload)
    lines = ["### PR review decision", ""]
    if plan.get("status") == "aborted":
        lines.append(f"- aborted: {plan.get('abort_reason')}")
    else:
        decision = plan.get("decision") or {}
        lines += [
            f"- risk: {decision.get('risk')}",
            f"- review: {decision.get('review_status')}",
            f"- verdict: {decision.get('verdict')}",
            f"- confidence: {_confidence(review)}",
            f"- auto-merge: {decision.get('auto_merge')}",
        ]
    if "results" in payload:
        results = payload["results"] + follow_up.get("results", [])
        lines.append(f"- labels applied: {_labels(*_written_labels(results))}")
        lines += ["", "**Actions**", "", *_action_lines(results)]
    elif plan.get("status") != "aborted":
        lines.append(
            f"- labels planned (dry run, nothing written): {_labels(*_planned_labels(plan))}"
        )
    lines += ["", "```json", json.dumps(payload, indent=2), "```"]
    return "\n".join(lines) + "\n"
