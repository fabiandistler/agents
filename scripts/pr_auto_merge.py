"""Decide whether the review bot enables or disables native auto-merge.

Auto-merge is the one narrow exception to "only the human merges": behind the
repository variable, for a low-risk pull request whose review passed. The
``auto-merge:bot`` label marks an auto-merge the bot enabled itself.
"""

from __future__ import annotations

import pr_risk
from pr_labels import AUTO_MERGE_BOT, DO_NOT_MERGE

# Branch deletion after the merge comes from the repository setting
# `delete_branch_on_merge`: the enablePullRequestAutoMerge mutation has no
# field for it.
AUTO_MERGE_METHOD = "merge"

GATES_HOLD = "hold"
GATES_UNKNOWN = "unknown"
GATES_FAIL = "fail"

# The auto-merge states a plan reports; the bot's label belongs to the first two.
BOT_STATES = ("enabled", "kept")

# Every function below takes a context that ``pr_plan`` validated: its labels
# are a list of strings.


def variable_enabled(value: object) -> bool:
    """The repository variable enables auto-merge only when it is exactly `true`."""
    return value is True or value == "true"


def _gates(context: dict, risk: str, review: dict, enabled: bool) -> str:
    """Return whether every auto-merge gate holds: hold, unknown or fail.

    Check results are no gate: the required checks in the default ruleset make
    native auto-merge wait for them, so pending checks never disable. The API
    reports mergeability as ``None`` while it is still computing it; that is
    unknown, which blocks enabling but never disables.
    """
    if not enabled or risk != pr_risk.LOW:
        return GATES_FAIL
    if review["status"] != "ok" or review["verdict"] != "pass":
        return GATES_FAIL
    if review.get("partial") is not False:
        return GATES_FAIL
    if context.get("fork") is not False or context.get("draft") is not False:
        return GATES_FAIL
    base_ref = context.get("base_ref")
    default_branch = context.get("default_branch")
    if not isinstance(base_ref, str) or base_ref != default_branch:
        return GATES_FAIL
    if context["reviews"]["changes_requested"]:
        return GATES_FAIL
    if DO_NOT_MERGE in context["labels"]:
        return GATES_FAIL
    mergeable = context.get("mergeable")
    if mergeable is None:
        return GATES_UNKNOWN
    return GATES_HOLD if mergeable is True else GATES_FAIL


def _state(context: dict, gates: str) -> str:
    """Decide the auto-merge state: enabled, kept, disabled, human or off.

    The ``auto-merge:bot`` label marks the bot's own auto-merge. An active
    auto-merge without it is a human's and is never taken over or disabled,
    except that ``do-not-merge`` disables any auto-merge.
    """
    labels = context["labels"]
    active = context.get("auto_merge_active") is True
    if active and DO_NOT_MERGE in labels:
        return "disabled"
    if active and AUTO_MERGE_BOT not in labels:
        return "human"
    if gates == GATES_HOLD:
        return "kept" if active else "enabled"
    if active:
        return "disabled" if gates == GATES_FAIL else "kept"
    return "off"


def _action(context: dict, state: str) -> dict | None:
    if state == "enabled":
        return {
            "kind": "enable_auto_merge",
            "pull_request_id": context["node_id"],
            "method": AUTO_MERGE_METHOD,
            "expected_head_oid": context["head_sha"],
        }
    if state == "disabled":
        return {"kind": "disable_auto_merge", "pull_request_id": context["node_id"]}
    return None


def plan_auto_merge(
    context: dict, risk: str, review: dict, variable: object, refused: bool
) -> tuple[str, dict | None]:
    """Return the auto-merge state and the action it needs, if any.

    ``kept`` and ``human`` need no write: the bot's auto-merge stays as it is,
    and a human's is left alone. ``refused`` means GitHub just refused to arm
    auto-merge because the pull request is already mergeable; the state that
    would enable it again becomes ``refused`` and waits for a human merge.
    """
    state = _state(context, _gates(context, risk, review, variable_enabled(variable)))
    if refused and state == "enabled":
        return "refused", None
    return state, _action(context, state)


def plan_hold(context: dict) -> tuple[str, dict | None]:
    """Return the hold's auto-merge state (disabled, human or off) and its action.

    The hold runs without a review: on a push, so a new head cannot merge
    before its review is published, and when ``do-not-merge`` is added. It
    disables the bot's auto-merge, or any auto-merge under ``do-not-merge``,
    and never enables one.
    """
    labels = context["labels"]
    if context.get("auto_merge_active") is not True:
        return "off", None
    if DO_NOT_MERGE in labels or AUTO_MERGE_BOT in labels:
        return "disabled", _action(context, "disabled")
    return "human", None
