"""Decide whether the review bot enables or disables native auto-merge.

Auto-merge is the one narrow exception to "only the human merges": behind the
repository variable, for a low-risk pull request whose review passed. The
``auto-merge:bot`` label marks an auto-merge the bot enabled itself.
"""

from __future__ import annotations

import pr_risk

DO_NOT_MERGE = "do-not-merge"
AUTO_MERGE_LABEL = "auto-merge:bot"
AUTO_MERGE_METHOD = "merge"
AUTO_MERGE_DELETE_BRANCH = True
REQUIRED_CHECKS = ("checks", "mermaid", "secrets")


def context_labels(context: dict) -> list[str]:
    """The label names on the pull request; anything else in the field is ignored."""
    labels = context.get("labels")
    if not isinstance(labels, list):
        return []
    return [label for label in labels if isinstance(label, str)]


def variable_enabled(value: object) -> bool:
    """The repository variable enables auto-merge only when it is exactly `true`."""
    return value is True or value == "true"


def _blocked(context: dict, risk: str, review: dict, enabled: bool) -> bool:
    if not enabled or risk != pr_risk.LOW:
        return True
    if review["status"] != "ok" or review["verdict"] != "pass":
        return True
    if review.get("partial") is not False:
        return True
    if context.get("fork") or context.get("draft"):
        return True
    if context.get("mergeable") is not True:
        return True
    base_ref = context.get("base_ref")
    default_branch = context.get("default_branch")
    if not isinstance(base_ref, str) or base_ref != default_branch:
        return True
    if context["reviews"]["changes_requested"]:
        return True
    if DO_NOT_MERGE in context_labels(context):
        return True
    checks = context.get("checks")
    if not isinstance(checks, dict):
        return True
    return any(checks.get(name) != "success" for name in REQUIRED_CHECKS)


def plan_auto_merge(
    context: dict, risk: str, review: dict, variable: object
) -> tuple[str, dict | None]:
    """Return the auto-merge state (enabled, disabled or off) and its action."""
    if not _blocked(context, risk, review, variable_enabled(variable)):
        action = {
            "kind": "enable_auto_merge",
            "method": AUTO_MERGE_METHOD,
            "delete_branch": AUTO_MERGE_DELETE_BRANCH,
        }
        return "enabled", action
    # Only the bot's own auto-merge is disabled, and only while GitHub still has
    # it on; a stale label without active auto-merge is just removed.
    if AUTO_MERGE_LABEL in context_labels(context) and context.get("auto_merge_active") is True:
        return "disabled", {"kind": "disable_auto_merge"}
    return "off", None
