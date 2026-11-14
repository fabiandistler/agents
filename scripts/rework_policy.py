"""The Rework task's gate rules, free of I/O (ADR-0015).

When the automated review of an implementer pull request (`agent/issue-<n>`)
ends with a non-pass verdict, the Rework task lets one model run fix exactly
the findings it was handed. ``decide`` says whether a review may start such a
run, must hand the pull request to a person, or stops without a write.

The counter lives on the pull request: before the model starts, the gate posts
one round marker naming the round and the reviewed head. Only markers by the
workflow bot count, so a person quoting one cannot spend or reset a round.
After ``MAX_REWORK_ROUNDS`` markers, the next non-pass verdict hands the pull
request to a person, once per head.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from check_pr_issue_links import closing_references
from issue_triage_policy import READY_FOR_HUMAN
from pr_comment import bot_comments
from pr_labels import DO_NOT_MERGE

MAX_REWORK_ROUNDS = 2

# The pull request author the implementer opens as: the Claude GitHub App.
APP_LOGIN = "claude[bot]"
BASE_BRANCH = "main"
REVIEW_WORKFLOW_PATH = ".github/workflows/pr-review.yml"
REVIEW_EVENT = "pull_request_target"
REWORK_VERDICTS = ("concerns", "block")

AGENT_BRANCH = re.compile(r"agent/issue-([1-9][0-9]*)")
HEAD_SHA = re.compile(r"[0-9a-f]{40}")
ROUND_MARKER = "<!-- rework-round:{round} head:{head} -->"
ROUND_MARKER_PATTERN = re.compile(r"<!-- rework-round:([1-9][0-9]*) head:([0-9a-f]{40}) -->")
HANDOFF_MARKER = "<!-- rework-handoff head:{head} -->"

PROCEED = "proceed"
HANDOFF = "handoff"
STOP = "stop"


@dataclass(frozen=True)
class Decision:
    """What the gate does: ``PROCEED`` with ``round``, ``HANDOFF``, or ``STOP``."""

    action: str
    reason: str
    issue: int | None = None
    round: int | None = None
    head_sha: str | None = None


def _stop(reason: str) -> Decision:
    return Decision(STOP, reason)


def agent_issue(pull: dict) -> int | None:
    """The issue number of an `agent/issue-<n>` head branch, or None for any other branch."""
    head = pull.get("head")
    ref = head.get("ref") if isinstance(head, dict) else None
    match = AGENT_BRANCH.fullmatch(ref) if isinstance(ref, str) else None
    return int(match[1]) if match else None


def linked_issue(pull: dict, repo: str) -> int | None:
    """The branch's issue when the body also closes it; None when the two disagree."""
    number = agent_issue(pull)
    body = pull.get("body")
    references = closing_references(body if isinstance(body, str) else "", repo)
    if number is None or f"{repo.lower()}#{number}" not in references:
        return None
    return number


def round_heads(comments: object) -> list[str]:
    """The head SHA of every round marker the workflow bot wrote, in comment order."""
    heads: list[str] = []
    for comment in bot_comments(comments):
        heads += [head for _, head in ROUND_MARKER_PATTERN.findall(comment["body"])]
    return heads


def handed_off(comments: object, head_sha: str) -> bool:
    marker = HANDOFF_MARKER.format(head=head_sha)
    return any(marker in comment["body"] for comment in bot_comments(comments))


def _labels(item: dict) -> set[str]:
    labels = item.get("labels")
    return {
        label.get("name")
        for label in (labels if isinstance(labels, list) else [])
        if isinstance(label, dict)
    }


def _run_stop(run: dict) -> str | None:
    if run.get("path") != REVIEW_WORKFLOW_PATH:
        return "the triggering run is not a pr-review run"
    if run.get("conclusion") != "success":
        return "the triggering run did not succeed"
    if run.get("event") != REVIEW_EVENT:
        return "the triggering run was not a pull request event"
    return None


def _review_stop(review: dict, context: dict, run: dict) -> str | None:
    if review.get("status") != "ok":
        return "the review did not complete"
    if review.get("verdict") not in REWORK_VERDICTS:
        return "the verdict is not concerns or block"
    findings = review.get("findings")
    if not isinstance(findings, list) or not findings:
        return "the review has no findings"
    head_sha = review.get("head_sha")
    if not isinstance(head_sha, str) or not HEAD_SHA.fullmatch(head_sha):
        return "the review names no head commit"
    if context.get("number") != review.get("number") or context.get("head_sha") != head_sha:
        return "the review and the pull request context disagree"
    # A pull_request_target run carries the pull request's head commit, so the
    # artifacts must name the head the triggering run was started for.
    if run.get("head_sha") != head_sha:
        return "the triggering run was for another commit"
    return None


def _field(item: dict, name: str) -> dict:
    value = item.get(name)
    return value if isinstance(value, dict) else {}


def _pull_stop(pull: dict, repo: str) -> str | None:
    head = _field(pull, "head")
    head_repo = _field(head, "repo").get("full_name")
    user = _field(pull, "user")
    if pull.get("state") != "open":
        return "the pull request is not open"
    if pull.get("draft") is not False:
        return "the pull request is a draft"
    if not isinstance(head_repo, str) or head_repo.lower() != repo.lower():
        return "the head branch lives in another repository"
    if _field(pull, "base").get("ref") != BASE_BRANCH:
        return "the pull request does not target main"
    if agent_issue(pull) is None:
        return "the head branch is not agent/issue-<n>"
    if user.get("login") != APP_LOGIN or user.get("type") != "Bot":
        return "the pull request was not opened by the Claude GitHub App"
    if DO_NOT_MERGE in _labels(pull):
        return "the pull request carries do-not-merge"
    if linked_issue(pull, repo) is None:
        return "the body does not close the branch's issue"
    return None


def decide(
    *,
    repo: str,
    run: dict,
    review: dict,
    context: dict,
    pull: dict,
    issue: dict | None,
    comments: object,
) -> Decision:
    """Decide the gate for one completed review.

    ``run`` is the triggering pr-review run (``path``, ``conclusion``, ``event``,
    ``head_sha``); ``review`` and ``context`` are its `pr-review` and
    `pr-context` artifacts; ``pull``, ``issue`` and ``comments`` are live
    REST payloads (comments as ``pr_github.comment_entry``). ``issue`` is
    None when no issue was fetched.
    """
    reason = _run_stop(run) or _review_stop(review, context, run) or _pull_stop(pull, repo)
    if reason:
        return _stop(reason)
    issue_number = linked_issue(pull, repo)
    if not isinstance(issue, dict) or issue.get("number") != issue_number:
        return _stop("the linked issue could not be read")
    if "pull_request" in issue:
        return _stop("the linked number is a pull request")
    if READY_FOR_HUMAN in _labels(issue):
        return _stop("the linked issue already waits for a person")
    head_sha = review["head_sha"]
    if _field(pull, "head").get("sha") != head_sha:
        return _stop("the pull request moved past the reviewed head")
    rounds = round_heads(comments)
    if head_sha in rounds:
        return _stop("a rework round already ran for this head")
    if handed_off(comments, head_sha):
        return _stop("the pull request was already handed to a person for this head")
    if len(rounds) >= MAX_REWORK_ROUNDS:
        return Decision(HANDOFF, "the rework rounds are used up", issue_number, None, head_sha)
    return Decision(
        PROCEED, "the review has findings to rework", issue_number, len(rounds) + 1, head_sha
    )


def round_marker(round_number: int, head_sha: str) -> str:
    return ROUND_MARKER.format(round=round_number, head=head_sha)


def handoff_comment(head_sha: str) -> str:
    return f"""\
{HANDOFF_MARKER.format(head=head_sha)}
> *This was generated by AI.*

The automated review of commit `{head_sha[:7]}` still has findings after \
{MAX_REWORK_ROUNDS} rework rounds, so no further rework run starts. The pull \
request and its issue now wait for a person: read the findings in the review \
comment, then fix them here or close the pull request.
"""


def round_comment(round_number: int, head_sha: str) -> str:
    return f"""\
{round_marker(round_number, head_sha)}
> *This was generated by AI.*

Rework round {round_number} of {MAX_REWORK_ROUNDS} starts for commit \
`{head_sha[:7]}`: a run fixes only the findings of the review comment and \
pushes to this branch.
"""
