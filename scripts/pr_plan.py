"""Plan the publish actions for one reviewed pull request.

The planner is model-free. It reads the risk decision produced by
``pr_risk.py`` and the review artifact produced by ``pr_review.py``, re-runs the
risk policy on a fresh context, and emits the exact list of actions it would
take: label changes, one sticky comment (``pr_comment.py``), a reviewer request
(or an assignment when the maintainer authored the pull request), and an
auto-merge enable or disable (``pr_auto_merge.py``). Nothing here writes to
GitHub; the plan is the whole output.
"""

from __future__ import annotations

import pr_auto_merge
import pr_comment
import pr_github
import pr_risk

SCHEMA_VERSION = 1

BOT_LOGIN = "fabiandistler"

RISK_PREFIX = "risk:"
VERDICT_PREFIX = "review:"
NEEDS_REVIEW = "needs-review"

REVIEW_STATUSES = ("ok", "unavailable", "skipped")
VERDICTS = ("pass", "concerns", "block")


class ArtifactError(ValueError):
    """A file could not be read, or an artifact has the wrong shape."""


# --- Validation --------------------------------------------------------------


def _require_mapping(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise ArtifactError(f"{name} is not a JSON object")
    if value.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ArtifactError(f"{name} has an unsupported schema_version")
    return value


def _validate_context(context: object) -> dict:
    context = _require_mapping(context, "context")
    repo = context.get("repo")
    if not isinstance(repo, str) or not pr_github.REPO_PATTERN.fullmatch(repo):
        raise ArtifactError("context is missing repo as OWNER/REPO")
    number = context.get("number")
    if isinstance(number, bool) or not isinstance(number, int):
        raise ArtifactError("context is missing an integer number")
    head_sha = context.get("head_sha")
    if not isinstance(head_sha, str) or not head_sha:
        raise ArtifactError("context is missing head_sha")
    reviews = context.get("reviews")
    if not isinstance(reviews, dict) or not isinstance(reviews.get("changes_requested"), bool):
        raise ArtifactError("context field 'reviews' must carry a boolean changes_requested")
    return context


def validate_assessment(assessment: object) -> dict:
    assessment = _require_mapping(assessment, "assessment")
    head_sha = assessment.get("head_sha")
    if not isinstance(head_sha, str) or not head_sha:
        raise ArtifactError("assessment is missing head_sha")
    if assessment.get("risk") not in pr_risk.RISK_ORDER:
        raise ArtifactError("assessment risk must be low, medium or high")
    return assessment


def validate_review(review: object) -> dict:
    review = _require_mapping(review, "review")
    status = review.get("status")
    if status not in REVIEW_STATUSES:
        raise ArtifactError("review status must be ok, unavailable or skipped")
    head_sha = review.get("head_sha")
    if head_sha is not None and (not isinstance(head_sha, str) or not head_sha):
        raise ArtifactError("review head_sha must be a non-empty string or null")
    if status == "ok":
        if review.get("risk") not in pr_risk.RISK_ORDER:
            raise ArtifactError("review risk must be low, medium or high")
        if review.get("verdict") not in VERDICTS:
            raise ArtifactError("review verdict must be pass, concerns or block")
    if not isinstance(review.get("partial", False), bool):
        raise ArtifactError("review partial must be a boolean")
    findings = review.get("findings", [])
    if not isinstance(findings, list) or not all(isinstance(item, dict) for item in findings):
        raise ArtifactError("review findings must be a list of objects")
    for field in ("summary", "raw"):
        if not isinstance(review.get(field), (str, type(None))):
            raise ArtifactError(f"review {field} must be a string or null")
    return review


# --- Decisions ---------------------------------------------------------------


def _raise_risk(current: str, candidate: str) -> str:
    return candidate if pr_risk.RISK_ORDER[candidate] > pr_risk.RISK_ORDER[current] else current


def _effective_risk(context: dict, review: dict) -> tuple[str, dict]:
    policy = pr_risk.classify_pull_request(context)
    if review["status"] != "ok":
        return policy["risk"], policy
    return _raise_risk(policy["risk"], review["risk"]), policy


def _verdict_label(review: dict) -> str | None:
    if review["status"] == "ok":
        return f"{VERDICT_PREFIX}{review['verdict']}"
    if review["status"] == "unavailable":
        return f"{VERDICT_PREFIX}unavailable"
    return None


def _needs_review(context: dict, risk: str, review: dict) -> bool:
    # A self-authored pull request cannot request the maintainer as a reviewer;
    # the assignment plus this label carry the signal instead.
    return (
        risk in (pr_risk.MEDIUM, pr_risk.HIGH)
        or review["status"] == "unavailable"
        or review.get("verdict") in ("concerns", "block")
        or context.get("author") == BOT_LOGIN
    )


def _plan_labels(
    context: dict,
    risk: str,
    review: dict,
    bot_auto_merge: bool,
) -> tuple[list[str], list[str]]:
    existing = pr_auto_merge.context_labels(context)
    add: list[str] = []
    remove: list[str] = []

    desired_risk = f"{RISK_PREFIX}{risk}"
    if desired_risk not in existing:
        add.append(desired_risk)
    remove.extend(
        label for label in existing if label.startswith(RISK_PREFIX) and label != desired_risk
    )

    desired_verdict = _verdict_label(review)
    if desired_verdict is None:
        remove.extend(label for label in existing if label.startswith(VERDICT_PREFIX))
    else:
        if desired_verdict not in existing:
            add.append(desired_verdict)
        remove.extend(
            label
            for label in existing
            if label.startswith(VERDICT_PREFIX) and label != desired_verdict
        )

    if _needs_review(context, risk, review):
        if NEEDS_REVIEW not in existing:
            add.append(NEEDS_REVIEW)
    elif NEEDS_REVIEW in existing:
        remove.append(NEEDS_REVIEW)

    bot_label = pr_auto_merge.AUTO_MERGE_LABEL
    if bot_auto_merge and bot_label not in existing:
        add.append(bot_label)
    if not bot_auto_merge and bot_label in existing:
        remove.append(bot_label)

    return add, remove


def _reviewer_action(context: dict) -> dict:
    if context.get("author") == BOT_LOGIN:
        return {"kind": "assign", "login": BOT_LOGIN}
    return {"kind": "request_reviewer", "login": BOT_LOGIN}


# --- Plan --------------------------------------------------------------------


def _plan(
    context: dict,
    status: str,
    abort_reason: str | None,
    actions: list[dict],
    decision: dict,
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "repo": context["repo"],
        "number": context["number"],
        "head_sha": context["head_sha"],
        "status": status,
        "abort_reason": abort_reason,
        "decision": decision,
        "actions": actions,
    }


def _decision(risk: str, review: dict, auto_merge: str) -> dict:
    return {
        "risk": risk,
        "review_status": review["status"],
        "verdict": review.get("verdict") if review["status"] == "ok" else None,
        "auto_merge": auto_merge,
    }


def _aborted_decision(review: dict) -> dict:
    return {
        "risk": None,
        "review_status": review["status"],
        "verdict": None,
        "auto_merge": "off",
    }


def _is_stale(assessment: dict, review: dict, head_sha: str) -> bool:
    if assessment["head_sha"] != head_sha:
        return True
    return review["head_sha"] is not None and review["head_sha"] != head_sha


def plan_publish(
    context: dict,
    assessment: dict,
    review: dict,
    auto_merge: bool | str | None = False,
) -> dict:
    """Return the planned actions for one pull request; never writes.

    ``auto_merge`` is the repository variable: only ``True`` or the string
    ``"true"`` enables auto-merge planning; ``None`` (unset) keeps it off.
    """
    context = _validate_context(context)
    assessment = validate_assessment(assessment)
    review = validate_review(review)

    if context.get("state") == "closed":
        return _plan(context, "aborted", "pull_request_closed", [], _aborted_decision(review))

    if _is_stale(assessment, review, context["head_sha"]):
        return _plan(
            context,
            "aborted",
            "head_sha_changed",
            [],
            _aborted_decision(review),
        )

    risk, policy = _effective_risk(context, review)
    auto_merge_state, auto_merge_action = pr_auto_merge.plan_auto_merge(
        context, risk, review, auto_merge
    )
    add, remove = _plan_labels(context, risk, review, auto_merge_state == "enabled")

    actions: list[dict] = []
    if add or remove:
        actions.append({"kind": "set_labels", "add": add, "remove": remove})
    comment = pr_comment.comment_action(context, risk, policy, review)
    if comment is not None:
        actions.append(comment)
    actions.append(_reviewer_action(context))
    if auto_merge_action is not None:
        actions.append(auto_merge_action)
    return _plan(
        context,
        "planned",
        None,
        actions,
        _decision(risk, review, auto_merge_state),
    )
