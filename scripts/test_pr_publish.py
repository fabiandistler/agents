"""Tests for the model-free publish decision (scripts/pr_publish.py).

The public seam is ``plan_publish(context, assessment, review, auto_merge)``
plus the CLI. Every test asserts the plan JSON, never a private helper, and no
test performs a network call.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pr_publish
import pytest

SCRIPT = Path(__file__).resolve().parent / "pr_publish.py"
MARKER = "<!-- pr-review-bot -->"
BOT = "fabiandistler"

ACTION_KINDS = {
    "set_labels",
    "upsert_comment",
    "request_reviewer",
    "assign",
    "enable_auto_merge",
    "disable_auto_merge",
}


def file_entry(
    path: str,
    *,
    status: str = "modified",
    additions: int = 1,
    deletions: int = 0,
    binary: bool = False,
    renamed_from: str | None = None,
) -> dict:
    return {
        "path": path,
        "status": status,
        "additions": additions,
        "deletions": deletions,
        "binary": binary,
        "renamed_from": renamed_from,
    }


def make_context(files: list[dict] | None = None, **overrides: object) -> dict:
    context = {
        "schema_version": 1,
        "repo": "fabiandistler/agents",
        "number": 42,
        "title": "A change",
        "body": "",
        "author": "someone-else",
        "head_sha": "abc123",
        "head_ref": "fix/x",
        "base_ref": "main",
        "default_branch": "main",
        "draft": False,
        "fork": False,
        "mergeable": True,
        "labels": [],
        "files": [file_entry("docs/guide.md")] if files is None else files,
        "diff": "",
        "base_files": {},
        "comments": [],
        "checks": {"checks": "success", "mermaid": "success", "secrets": "success"},
        "reviews": {"changes_requested": False},
    }
    context.update(overrides)
    return context


def make_assessment(**overrides: object) -> dict:
    assessment = {
        "schema_version": 1,
        "number": 42,
        "head_sha": "abc123",
        "risk": "low",
        "reasons": ["docs: docs/guide.md"],
        "auto_merge_eligible": True,
        "counts": {"files": 1, "additions": 1, "deletions": 0, "changed_lines": 1},
    }
    assessment.update(overrides)
    return assessment


def make_review(**overrides: object) -> dict:
    review = {
        "schema_version": 1,
        "number": 42,
        "head_sha": "abc123",
        "status": "ok",
        "risk": "low",
        "verdict": "pass",
        "summary": "The documentation change is accurate and complete.",
        "findings": [
            {
                "path": "docs/guide.md",
                "line": 12,
                "severity": "info",
                "message": "The heading could name the command it documents.",
                "suggestion": "Use the command name in the heading.",
            }
        ],
        "partial": False,
        "raw": None,
    }
    review.update(overrides)
    return review


def actions_of(plan: dict, kind: str) -> list[dict]:
    return [action for action in plan["actions"] if action["kind"] == kind]


def label_action(plan: dict) -> dict:
    labels = actions_of(plan, "set_labels")
    assert len(labels) == 1
    return labels[0]


def comment_action(plan: dict) -> dict:
    comments = actions_of(plan, "upsert_comment")
    assert len(comments) == 1
    return comments[0]


# --- Plan shape and identity -------------------------------------------------


def test_plan_has_the_documented_shape():
    plan = pr_publish.plan_publish(make_context(), make_assessment(), make_review())

    assert set(plan) == {
        "schema_version",
        "repo",
        "number",
        "head_sha",
        "status",
        "abort_reason",
        "decision",
        "actions",
    }
    assert plan["schema_version"] == 1
    assert plan["repo"] == "fabiandistler/agents"
    assert plan["number"] == 42
    assert plan["head_sha"] == "abc123"
    assert plan["status"] == "planned"
    assert plan["abort_reason"] is None


def test_plan_carries_the_decision_for_the_step_summary():
    plan = pr_publish.plan_publish(make_context(), make_assessment(), make_review())

    assert plan["decision"] == {
        "risk": "low",
        "review_status": "ok",
        "verdict": "pass",
        "auto_merge": "off",
    }


def test_decision_reports_enabled_auto_merge():
    plan = pr_publish.plan_publish(
        make_context(), make_assessment(), make_review(), auto_merge=True
    )

    assert plan["decision"]["auto_merge"] == "enabled"


def test_decision_reports_disabled_auto_merge():
    context = make_context(labels=["risk:low", "review:pass", "auto-merge:bot"])

    plan = pr_publish.plan_publish(context, make_assessment(), make_review(), auto_merge=False)

    assert plan["decision"]["auto_merge"] == "disabled"


def test_decision_reports_the_effective_risk_and_verdict():
    plan = pr_publish.plan_publish(
        make_context(), make_assessment(), make_review(risk="high", verdict="concerns")
    )

    assert plan["decision"]["risk"] == "high"
    assert plan["decision"]["verdict"] == "concerns"


def test_aborted_plan_has_no_decision_to_apply():
    plan = pr_publish.plan_publish(
        make_context(head_sha="def456"),
        make_assessment(head_sha="abc123"),
        make_review(head_sha="abc123"),
    )

    assert plan["decision"] == {
        "risk": None,
        "review_status": "ok",
        "verdict": None,
        "auto_merge": "off",
    }


def test_plan_uses_only_the_documented_action_kinds():
    plan = pr_publish.plan_publish(make_context(), make_assessment(), make_review())

    assert {action["kind"] for action in plan["actions"]} <= ACTION_KINDS
    assert not any(
        word in action["kind"] for action in plan["actions"] for word in ("approve", "change")
    )


def test_docs_pull_request_plans_labels_comment_and_reviewer():
    plan = pr_publish.plan_publish(make_context(), make_assessment(), make_review())

    assert [action["kind"] for action in plan["actions"]] == [
        "set_labels",
        "upsert_comment",
        "request_reviewer",
    ]
    assert label_action(plan)["add"] == ["risk:low", "review:pass"]
    assert label_action(plan)["remove"] == []
    assert actions_of(plan, "request_reviewer") == [{"kind": "request_reviewer", "login": BOT}]
    assert comment_action(plan)["comment_id"] is None
    assert comment_action(plan)["marker"] == MARKER


# --- Staleness ---------------------------------------------------------------


def test_stale_assessment_sha_aborts_every_action():
    plan = pr_publish.plan_publish(
        make_context(head_sha="def456"),
        make_assessment(head_sha="abc123"),
        make_review(head_sha="abc123"),
        auto_merge=True,
    )

    assert plan["status"] == "aborted"
    assert plan["abort_reason"] == "head_sha_changed"
    assert plan["actions"] == []
    assert plan["head_sha"] == "def456"


def test_stale_review_sha_aborts_every_action():
    plan = pr_publish.plan_publish(
        make_context(head_sha="def456"),
        make_assessment(head_sha="def456"),
        make_review(head_sha="abc123"),
    )

    assert plan["status"] == "aborted"
    assert plan["abort_reason"] == "head_sha_changed"
    assert plan["actions"] == []


def test_review_without_a_head_sha_does_not_abort():
    plan = pr_publish.plan_publish(
        make_context(),
        make_assessment(),
        make_review(status="skipped", head_sha=None, risk=None, verdict=None, findings=[]),
    )

    assert plan["status"] == "planned"
    assert plan["abort_reason"] is None


# --- Risk and verdict labels -------------------------------------------------


def test_fresh_policy_overrides_the_assessment_risk():
    plan = pr_publish.plan_publish(
        make_context(),
        make_assessment(risk="high"),
        make_review(),
    )

    assert label_action(plan)["add"] == ["risk:low", "review:pass"]


def test_review_risk_never_lowers_the_policy_risk():
    context = make_context(files=[file_entry(".github/workflows/ci.yml")])

    plan = pr_publish.plan_publish(context, make_assessment(), make_review(risk="low"))

    labels = label_action(plan)
    assert "risk:high" in labels["add"]
    assert actions_of(plan, "enable_auto_merge") == []


def test_review_risk_raises_the_policy_risk():
    plan = pr_publish.plan_publish(
        make_context(),
        make_assessment(),
        make_review(risk="high", verdict="concerns"),
    )

    labels = label_action(plan)
    assert "risk:high" in labels["add"]
    assert "risk:low" not in labels["add"]
    assert "needs-review" in labels["add"]


def test_risk_label_family_is_replaced_not_accumulated():
    context = make_context(labels=["risk:high", "review:block", "needs-review"])

    plan = pr_publish.plan_publish(context, make_assessment(), make_review())

    labels = label_action(plan)
    assert labels["add"] == ["risk:low", "review:pass"]
    assert labels["remove"] == ["risk:high", "review:block", "needs-review"]


def test_verdict_label_family_is_replaced_without_touching_risk():
    context = make_context(labels=["risk:low", "review:pass"])
    review = make_review(verdict="concerns")

    plan = pr_publish.plan_publish(context, make_assessment(), review)

    labels = label_action(plan)
    assert labels["add"] == ["review:concerns", "needs-review"]
    assert labels["remove"] == ["review:pass"]


def test_already_correct_labels_plan_no_label_action():
    context = make_context(labels=["risk:low", "review:pass"])

    plan = pr_publish.plan_publish(context, make_assessment(), make_review())

    assert actions_of(plan, "set_labels") == []


def test_unavailable_review_labels_review_unavailable_and_needs_review():
    review = make_review(
        status="unavailable",
        risk="high",
        verdict=None,
        summary="Review unavailable: the provider call failed.",
        findings=[],
    )

    plan = pr_publish.plan_publish(make_context(), make_assessment(), review)

    labels = label_action(plan)
    assert "review:unavailable" in labels["add"]
    assert "needs-review" in labels["add"]
    assert not any(label.startswith("review:pass") for label in labels["add"])


def test_unavailable_review_replaces_a_stale_verdict_label():
    context = make_context(labels=["review:pass"])
    review = make_review(
        status="unavailable",
        risk="high",
        verdict=None,
        summary="Review unavailable: the provider call failed.",
        findings=[],
    )

    plan = pr_publish.plan_publish(context, make_assessment(), review)

    labels = label_action(plan)
    assert "review:unavailable" in labels["add"]
    assert labels["remove"] == ["review:pass"]


def test_skipped_review_plans_no_verdict_label():
    context = make_context(draft=True, labels=["review:concerns"])
    review = make_review(
        status="skipped",
        risk=None,
        verdict=None,
        summary="Review skipped: the pull request is a draft.",
        findings=[],
    )

    plan = pr_publish.plan_publish(context, make_assessment(), review)

    labels = label_action(plan)
    assert labels["add"] == ["risk:low"]
    assert labels["remove"] == ["review:concerns"]


# --- Reviewer or assignee ----------------------------------------------------


def test_self_authored_pull_request_is_assigned_and_needs_review():
    context = make_context(author=BOT, files=[file_entry("skills/x/SKILL.md")])
    review = make_review(risk="medium", verdict="concerns")

    plan = pr_publish.plan_publish(context, make_assessment(), review)

    assert actions_of(plan, "request_reviewer") == []
    assert actions_of(plan, "assign") == [{"kind": "assign", "login": BOT}]
    assert "needs-review" in label_action(plan)["add"]


def test_self_authored_low_risk_pull_request_still_carries_needs_review():
    context = make_context(author=BOT)

    plan = pr_publish.plan_publish(context, make_assessment(), make_review())

    assert actions_of(plan, "assign") == [{"kind": "assign", "login": BOT}]
    assert "needs-review" in label_action(plan)["add"]


def test_foreign_pull_request_requests_the_maintainer_as_reviewer():
    context = make_context(author="octocat")

    plan = pr_publish.plan_publish(context, make_assessment(), make_review())

    assert actions_of(plan, "assign") == []
    assert actions_of(plan, "request_reviewer") == [{"kind": "request_reviewer", "login": BOT}]


# --- Auto-merge gates --------------------------------------------------------

AUTO_MERGE_BLOCKERS = [
    ("variable off", {"auto_merge": False}, {}, {}),
    ("risk medium", {}, {"files": [file_entry("skills/x/SKILL.md")]}, {}),
    ("risk high", {}, {"files": [file_entry(".github/workflows/ci.yml")]}, {}),
    ("review raises the risk", {}, {}, {"risk": "high"}),
    ("verdict concerns", {}, {}, {"verdict": "concerns"}),
    ("verdict block", {}, {}, {"verdict": "block"}),
    ("partial review", {}, {}, {"partial": True}),
    ("fork", {}, {"fork": True}, {}),
    ("draft", {}, {"draft": True}, {}),
    ("not mergeable", {}, {"mergeable": False}, {}),
    ("mergeability unknown", {}, {"mergeable": None}, {}),
    ("wrong base branch", {}, {"base_ref": "release"}, {}),
    ("human change request", {}, {"reviews": {"changes_requested": True}}, {}),
    ("do-not-merge label", {}, {"labels": ["do-not-merge"]}, {}),
    (
        "checks failing",
        {},
        {"checks": {"checks": "failure", "mermaid": "success", "secrets": "success"}},
        {},
    ),
    (
        "checks pending",
        {},
        {"checks": {"checks": "pending", "mermaid": "success", "secrets": "success"}},
        {},
    ),
    (
        "checks missing",
        {},
        {"checks": {"mermaid": "success", "secrets": "success"}},
        {},
    ),
    (
        "mermaid failing",
        {},
        {"checks": {"checks": "success", "mermaid": "failure", "secrets": "success"}},
        {},
    ),
    (
        "secrets skipped",
        {},
        {"checks": {"checks": "success", "mermaid": "success", "secrets": "skipped"}},
        {},
    ),
    (
        "review unavailable",
        {},
        {},
        {
            "status": "unavailable",
            "risk": "high",
            "verdict": None,
            "summary": "Review unavailable: the provider call failed.",
            "findings": [],
        },
    ),
    (
        "review skipped",
        {},
        {},
        {
            "status": "skipped",
            "risk": None,
            "verdict": None,
            "summary": "Review skipped: the pull request is a draft.",
            "findings": [],
        },
    ),
]


@pytest.mark.parametrize(
    ("auto_merge", "context_overrides", "review_overrides"),
    [case[1:] for case in AUTO_MERGE_BLOCKERS],
    ids=[case[0] for case in AUTO_MERGE_BLOCKERS],
)
def test_every_auto_merge_gate_blocks(auto_merge, context_overrides, review_overrides):
    plan = pr_publish.plan_publish(
        make_context(**context_overrides),
        make_assessment(),
        make_review(**review_overrides),
        auto_merge=auto_merge,
    )

    assert actions_of(plan, "enable_auto_merge") == []


def test_low_risk_pass_enables_native_auto_merge():
    plan = pr_publish.plan_publish(
        make_context(), make_assessment(), make_review(), auto_merge=True
    )

    assert [action["kind"] for action in plan["actions"]] == [
        "set_labels",
        "upsert_comment",
        "request_reviewer",
        "enable_auto_merge",
    ]
    assert plan["actions"][-1] == {
        "kind": "enable_auto_merge",
        "method": "merge",
        "delete_branch": True,
    }
    assert label_action(plan)["add"] == ["risk:low", "review:pass", "auto-merge:bot"]


def test_auto_merge_variable_must_be_exactly_true():
    for value in ("TRUE", "True", "1", "yes", "", None):
        plan = pr_publish.plan_publish(
            make_context(), make_assessment(), make_review(), auto_merge=value
        )
        assert actions_of(plan, "enable_auto_merge") == [], value

    enabled = pr_publish.plan_publish(
        make_context(), make_assessment(), make_review(), auto_merge="true"
    )
    assert len(actions_of(enabled, "enable_auto_merge")) == 1


def test_a_raised_risk_disables_the_bots_auto_merge():
    context = make_context(
        files=[file_entry("skills/x/SKILL.md")],
        labels=["risk:low", "review:pass", "auto-merge:bot"],
    )

    plan = pr_publish.plan_publish(context, make_assessment(), make_review(), auto_merge=True)

    assert actions_of(plan, "disable_auto_merge") == [{"kind": "disable_auto_merge"}]
    labels = label_action(plan)
    assert "auto-merge:bot" in labels["remove"]
    assert "auto-merge:bot" not in labels["add"]
    assert "risk:medium" in labels["add"]


def test_turning_the_variable_off_disables_the_bots_auto_merge():
    context = make_context(labels=["risk:low", "review:pass", "auto-merge:bot"])

    plan = pr_publish.plan_publish(context, make_assessment(), make_review(), auto_merge=False)

    assert actions_of(plan, "disable_auto_merge") == [{"kind": "disable_auto_merge"}]
    assert "auto-merge:bot" in label_action(plan)["remove"]


def test_do_not_merge_is_never_removed_by_the_publisher():
    context = make_context(labels=["do-not-merge"])

    plan = pr_publish.plan_publish(context, make_assessment(), make_review())

    labels = label_action(plan)
    assert "do-not-merge" not in labels["add"]
    assert "do-not-merge" not in labels["remove"]
    assert actions_of(plan, "enable_auto_merge") == []


def test_a_human_enabled_auto_merge_is_never_touched():
    context = make_context(labels=["risk:low", "review:pass"])

    plan = pr_publish.plan_publish(context, make_assessment(), make_review(), auto_merge=False)

    assert actions_of(plan, "disable_auto_merge") == []
    assert actions_of(plan, "set_labels") == []


def test_auto_merge_is_not_enabled_twice():
    context = make_context(labels=["risk:low", "review:pass", "auto-merge:bot"])

    plan = pr_publish.plan_publish(context, make_assessment(), make_review(), auto_merge=True)

    assert len(actions_of(plan, "enable_auto_merge")) == 1
    assert actions_of(plan, "set_labels") == []


# --- Sticky comment ----------------------------------------------------------


def comment_body(plan: dict) -> str:
    return comment_action(plan)["body"]


def test_comment_starts_with_the_marker_and_states_risk_and_verdict():
    plan = pr_publish.plan_publish(make_context(), make_assessment(), make_review())

    body = comment_body(plan)
    assert body.startswith(MARKER)
    assert "risk **low**" in body
    assert "verdict **pass**" in body
    assert "abc123" in body


def test_comment_carries_the_summary_and_the_policy_reasons():
    plan = pr_publish.plan_publish(make_context(), make_assessment(), make_review())

    body = comment_body(plan)
    assert "The documentation change is accurate and complete." in body
    assert "docs: docs/guide.md" in body


def test_comment_lists_findings_with_location_severity_message_and_fix():
    plan = pr_publish.plan_publish(make_context(), make_assessment(), make_review())

    body = comment_body(plan)
    assert "`docs/guide.md:12`" in body
    assert "**info**" in body
    assert "The heading could name the command it documents." in body
    assert "Fix: Use the command name in the heading." in body


def test_comment_renders_a_finding_without_a_line_or_a_suggestion():
    review = make_review(
        findings=[
            {
                "path": "docs/guide.md",
                "line": None,
                "severity": "warning",
                "message": "The example is stale.",
                "suggestion": "",
            }
        ]
    )

    body = comment_body(pr_publish.plan_publish(make_context(), make_assessment(), review))

    assert "`docs/guide.md`" in body
    assert "`docs/guide.md:None`" not in body
    assert "Fix:" not in body


def test_comment_says_the_bot_never_approves_or_merges_directly():
    body = comment_body(pr_publish.plan_publish(make_context(), make_assessment(), make_review()))

    assert "never approves" in body
    assert "never merges" in body


def test_comment_reports_a_review_that_raised_the_risk():
    review = make_review(risk="high", verdict="concerns")

    body = comment_body(pr_publish.plan_publish(make_context(), make_assessment(), review))

    assert "risk **high**" in body
    assert "raised the risk from low to high" in body


def test_comment_warns_about_a_partial_review():
    review = make_review(partial=True)

    plan = pr_publish.plan_publish(make_context(), make_assessment(), review, auto_merge=True)

    assert "Partial review" in comment_body(plan)
    assert actions_of(plan, "enable_auto_merge") == []


def test_comment_reports_an_unavailable_review():
    review = make_review(
        status="unavailable",
        risk="high",
        verdict=None,
        summary="Review unavailable: the provider is not configured.",
        findings=[],
    )

    body = comment_body(pr_publish.plan_publish(make_context(), make_assessment(), review))

    assert "review unavailable" in body
    assert "Review unavailable: the provider is not configured." in body
    assert "Auto-merge stays off until a review succeeds." in body
    assert "**Findings**" not in body


def test_comment_reports_a_skipped_draft_review():
    context = make_context(draft=True)
    review = make_review(
        status="skipped",
        risk=None,
        verdict=None,
        summary="Review skipped: the pull request is a draft.",
        findings=[],
    )

    body = comment_body(pr_publish.plan_publish(context, make_assessment(), review))

    assert "review skipped" in body
    assert "Review skipped: the pull request is a draft." in body
    assert "Auto-merge stays off until the pull request is ready for review." in body


def test_comment_reports_a_skipped_fork_review():
    context = make_context(fork=True)
    review = make_review(
        status="skipped",
        risk=None,
        verdict=None,
        summary="Review skipped: the pull request comes from a fork.",
        findings=[],
    )

    body = comment_body(pr_publish.plan_publish(context, make_assessment(), review))

    assert "Fork pull requests are never auto-merged." in body


def test_comment_shows_an_unparseable_response_verbatim():
    review = make_review(
        risk="high",
        verdict="concerns",
        summary="",
        findings=[],
        raw="RISK low\nlooks fine to me",
    )

    body = comment_body(pr_publish.plan_publish(make_context(), make_assessment(), review))

    assert "could not be parsed" in body
    assert "RISK low\nlooks fine to me" in body


def test_unchanged_sticky_comment_plans_no_comment_action():
    first = pr_publish.plan_publish(make_context(), make_assessment(), make_review())
    body = comment_body(first)
    context = make_context(comments=[{"id": 7, "body": body}])

    second = pr_publish.plan_publish(context, make_assessment(), make_review())

    assert actions_of(second, "upsert_comment") == []


def test_existing_sticky_comment_is_updated_in_place():
    context = make_context(comments=[{"id": 7, "body": f"{MARKER}\nold assessment"}])

    plan = pr_publish.plan_publish(context, make_assessment(), make_review())

    comment = comment_action(plan)
    assert comment["comment_id"] == 7
    assert "old assessment" not in comment["body"]


def test_comment_ignores_comments_without_the_marker():
    context = make_context(
        comments=[
            {"id": 1, "body": "Looks good to me."},
            {"id": 7, "body": f"{MARKER}\nold assessment"},
        ]
    )

    plan = pr_publish.plan_publish(context, make_assessment(), make_review())

    assert comment_action(plan)["comment_id"] == 7


def test_comment_body_does_not_depend_on_the_auto_merge_decision():
    quiet = pr_publish.plan_publish(make_context(), make_assessment(), make_review())
    merging = pr_publish.plan_publish(
        make_context(), make_assessment(), make_review(), auto_merge=True
    )

    assert comment_body(quiet) == comment_body(merging)


# --- Live path ---------------------------------------------------------------

REPO = "fabiandistler/agents"
NUMBER = 42
PR_PATH = f"/repos/{REPO}/pulls/{NUMBER}"
FILES_PATH = f"{PR_PATH}/files"
COMMENTS_PATH = f"/repos/{REPO}/issues/{NUMBER}/comments"
REVIEWS_PATH = f"{PR_PATH}/reviews"
CONTENTS_PREFIX = f"/repos/{REPO}/contents/"


def json_response(payload: object) -> pr_publish.pr_github.Response:
    return pr_publish.pr_github.Response(status=200, body=json.dumps(payload).encode("utf-8"))


def pull_request(head_sha: str, labels: list[str]) -> dict:
    return {
        "title": "A change",
        "body": "",
        "user": {"login": "someone-else"},
        "head": {"sha": head_sha, "ref": "fix/x", "repo": {"full_name": REPO}},
        "base": {
            "sha": "base123",
            "ref": "main",
            "repo": {"full_name": REPO, "default_branch": "main"},
        },
        "draft": False,
        "mergeable": True,
        "labels": [{"name": label} for label in labels],
    }


class FakeGitHub:
    """Serves ``fetch_context`` from canned payloads and records every write."""

    def __init__(self, head_shas: list[str], labels: list[str] | None = None) -> None:
        self.head_shas = list(head_shas)
        self.labels = list(labels or [])
        self.calls: list[dict] = []
        self.pull_fetches = 0
        self.fail_paths: set[str] = set()

    def get(self, path: str, params: dict | None = None, accept: str | None = None):
        self.calls.append({"method": "GET", "path": path, "payload": None})
        if path == PR_PATH and accept is None:
            self.pull_fetches += 1
            return json_response(pull_request(self.head_shas.pop(0), self.labels))
        if path == PR_PATH:
            return pr_publish.pr_github.Response(status=200, body=b"diff --git a/x b/x\n")
        if path == FILES_PATH:
            return json_response(
                [
                    {
                        "filename": "docs/guide.md",
                        "status": "modified",
                        "additions": 1,
                        "deletions": 0,
                        "patch": "@@",
                    }
                ]
            )
        if path == COMMENTS_PATH:
            return json_response([])
        if path == REVIEWS_PATH:
            return json_response([])
        if path.endswith("/check-runs"):
            return json_response({"check_runs": []})
        if path.startswith(CONTENTS_PREFIX):
            raise pr_publish.pr_github.FetchError("not found", status=404)
        raise AssertionError(f"unexpected GET {path}")

    def _write(self, method: str, path: str, payload: dict | None):
        self.calls.append({"method": method, "path": path, "payload": payload})
        if path in self.fail_paths:
            raise pr_publish.pr_github.FetchError("server error", status=500)
        return pr_publish.pr_github.Response(status=200, body=b"{}")

    def post(self, path: str, payload: dict | None = None):
        return self._write("POST", path, payload)

    def patch(self, path: str, payload: dict | None = None):
        return self._write("PATCH", path, payload)

    def delete(self, path: str, payload: dict | None = None):
        return self._write("DELETE", path, payload)


def write_calls(fake: FakeGitHub) -> list[dict]:
    return [call for call in fake.calls if call["method"] != "GET"]


def test_live_dry_run_fetches_once_and_writes_nothing():
    fake = FakeGitHub(["abc123"])

    plan = pr_publish.publish_live(REPO, NUMBER, make_assessment(), make_review(), client=fake)

    assert plan["status"] == "planned"
    assert plan["head_sha"] == "abc123"
    assert fake.pull_fetches == 1
    assert write_calls(fake) == []


def test_live_write_applies_exactly_the_planned_actions():
    fake = FakeGitHub(["abc123", "abc123"])

    payload = pr_publish.publish_live(
        REPO, NUMBER, make_assessment(), make_review(), write=True, client=fake
    )

    assert payload["schema_version"] == 1
    assert payload["plan"]["status"] == "planned"
    assert payload["ok"] is True
    assert [result["kind"] for result in payload["results"]] == [
        "set_labels",
        "upsert_comment",
        "request_reviewer",
    ]
    assert fake.pull_fetches == 2
    assert [call["method"] for call in write_calls(fake)] == [
        "POST",
        "POST",
        "POST",
        "POST",
        "POST",
    ]
    assert write_calls(fake)[0]["path"] == f"/repos/{REPO}/labels"
    assert write_calls(fake)[2]["path"] == f"/repos/{REPO}/issues/{NUMBER}/labels"
    assert write_calls(fake)[3]["path"] == COMMENTS_PATH
    assert write_calls(fake)[4]["path"] == f"/repos/{REPO}/pulls/{NUMBER}/requested_reviewers"


def test_a_changed_head_sha_between_the_fetches_aborts_every_write():
    fake = FakeGitHub(["abc123", "def456"])

    payload = pr_publish.publish_live(
        REPO, NUMBER, make_assessment(), make_review(), write=True, client=fake
    )

    assert payload["status"] == "aborted"
    assert payload["abort_reason"] == "head_sha_changed"
    assert payload["actions"] == []
    assert payload["head_sha"] == "def456"
    assert fake.pull_fetches == 2
    assert write_calls(fake) == []


def test_a_stale_assessment_aborts_before_the_second_fetch():
    fake = FakeGitHub(["def456"])

    payload = pr_publish.publish_live(
        REPO,
        NUMBER,
        make_assessment(head_sha="abc123"),
        make_review(head_sha="abc123"),
        write=True,
        client=fake,
    )

    assert payload["status"] == "aborted"
    assert payload["abort_reason"] == "head_sha_changed"
    assert fake.pull_fetches == 1
    assert write_calls(fake) == []


def test_a_failed_write_is_reported_in_the_results():
    fake = FakeGitHub(["abc123", "abc123"])
    fake.fail_paths.add(f"/repos/{REPO}/labels")

    payload = pr_publish.publish_live(
        REPO, NUMBER, make_assessment(), make_review(), write=True, client=fake
    )

    assert payload["ok"] is False
    assert [result["ok"] for result in payload["results"]] == [False, True, True]


# --- CLI ---------------------------------------------------------------------


def write_json(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def run_cli(*args: str, **env: str) -> subprocess.CompletedProcess:
    clean_env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PR_AUTO_MERGE", "GITHUB_TOKEN"}
    }
    clean_env.update(env)
    return subprocess.run(  # noqa: S603 -- test invokes its own script with argv, no shell.
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=clean_env,
        check=False,
    )


def offline_args(tmp_path: Path) -> list[str]:
    return [
        "--context",
        str(write_json(tmp_path, "context.json", make_context())),
        "--assessment",
        str(write_json(tmp_path, "assessment.json", make_assessment())),
        "--review",
        str(write_json(tmp_path, "review.json", make_review())),
    ]


def test_cli_prints_the_plan_json(tmp_path):
    run = run_cli(*offline_args(tmp_path))

    assert run.returncode == 0, run.stderr
    assert run.stderr == ""
    plan = json.loads(run.stdout)
    assert plan["status"] == "planned"
    assert plan["number"] == 42
    assert plan["head_sha"] == "abc123"
    assert [action["kind"] for action in plan["actions"]] == [
        "set_labels",
        "upsert_comment",
        "request_reviewer",
    ]


def test_cli_prints_an_aborted_plan_and_still_exits_zero(tmp_path):
    assessment = write_json(tmp_path, "assessment.json", make_assessment(head_sha="stale"))
    run = run_cli(
        "--context",
        str(write_json(tmp_path, "context.json", make_context())),
        "--assessment",
        str(assessment),
        "--review",
        str(write_json(tmp_path, "review.json", make_review())),
    )

    assert run.returncode == 0, run.stderr
    plan = json.loads(run.stdout)
    assert plan["status"] == "aborted"
    assert plan["actions"] == []


def test_cli_help_is_short_and_documents_exit_codes():
    run = run_cli("--help")

    assert run.returncode == 0
    assert run.stderr == ""
    assert len(run.stdout.splitlines()) < 25
    assert "usage:" in run.stdout
    assert "exit:" in run.stdout
    assert "1 a write action failed" in run.stdout
    assert "--write" in run.stdout
    assert run.stdout.count("python3 scripts/pr_publish.py") == 2


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--live"],
        ["--assessment", "a.json", "--review", "r.json"],
        ["--context", "c.json", "--assessment", "a.json"],
        ["--context", "c.json", "--review", "r.json"],
        ["--context", "c.json", "--live", "--repo", "o/r", "--pr", "1", "--assessment", "a"],
        ["--live", "--repo", "o/r", "--assessment", "a", "--review", "r"],
        ["--live", "--pr", "1", "--assessment", "a", "--review", "r"],
        ["--context", "c.json", "--pr", "1", "--assessment", "a", "--review", "r"],
        ["--context", "c.json", "--assessment", "a", "--review", "r", "--unknown"],
        ["--context", "c.json", "--assessment", "a", "--review", "r", "--live"],
    ],
)
def test_cli_usage_errors_exit_two(arguments):
    run = run_cli(*arguments)

    assert run.returncode == 2
    assert run.stdout == ""
    assert "usage:" in run.stderr


def test_cli_unreadable_context_exits_three(tmp_path):
    run = run_cli(
        "--context",
        str(tmp_path / "missing.json"),
        "--assessment",
        str(write_json(tmp_path, "assessment.json", make_assessment())),
        "--review",
        str(write_json(tmp_path, "review.json", make_review())),
    )

    assert run.returncode == 3
    assert "--context" in run.stderr


def test_cli_invalid_json_exits_three(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    run = run_cli(
        "--context",
        str(bad),
        "--assessment",
        str(write_json(tmp_path, "assessment.json", make_assessment())),
        "--review",
        str(write_json(tmp_path, "review.json", make_review())),
    )

    assert run.returncode == 3


def test_cli_malformed_artifact_exits_three(tmp_path):
    run = run_cli(
        "--context",
        str(write_json(tmp_path, "context.json", make_context())),
        "--assessment",
        str(write_json(tmp_path, "assessment.json", {"schema_version": 1})),
        "--review",
        str(write_json(tmp_path, "review.json", make_review())),
    )

    assert run.returncode == 3
    assert "--assessment" in run.stderr or "assessment" in run.stderr


def test_cli_live_fetch_failure_exits_four(monkeypatch, tmp_path):
    def fail(repo, number, token=None):
        raise pr_publish.pr_github.FetchError("boom")

    monkeypatch.setattr(pr_publish.pr_github, "fetch_context", fail)

    code = pr_publish.main(
        [
            "--live",
            "--repo",
            "fabiandistler/agents",
            "--pr",
            "42",
            "--assessment",
            str(write_json(tmp_path, "assessment.json", make_assessment())),
            "--review",
            str(write_json(tmp_path, "review.json", make_review())),
        ]
    )

    assert code == 4


def test_cli_live_plan_uses_the_fetched_context(monkeypatch, tmp_path, capsys):
    fetched = make_context(head_sha="fresh456", labels=["risk:high"])

    def fetch(repo, number, token=None):
        assert (repo, number) == ("fabiandistler/agents", 42)
        return fetched

    monkeypatch.setattr(pr_publish.pr_github, "fetch_context", fetch)
    assessment = write_json(tmp_path, "assessment.json", make_assessment(head_sha="fresh456"))

    code = pr_publish.main(
        [
            "--live",
            "--repo",
            "fabiandistler/agents",
            "--pr",
            "42",
            "--assessment",
            str(assessment),
            "--review",
            str(write_json(tmp_path, "review.json", make_review(head_sha="fresh456"))),
        ]
    )

    assert code == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["head_sha"] == "fresh456"
    assert plan["status"] == "planned"


def test_cli_reads_auto_merge_from_the_environment(tmp_path):
    args = offline_args(tmp_path)

    enabled = run_cli(*args, PR_AUTO_MERGE="true")
    assert "enable_auto_merge" in enabled.stdout

    disabled = run_cli(*args, PR_AUTO_MERGE="TRUE")
    assert "enable_auto_merge" not in disabled.stdout


# --- CLI write path ----------------------------------------------------------


def live_args(tmp_path: Path) -> list[str]:
    return [
        "--live",
        "--repo",
        REPO,
        "--pr",
        str(NUMBER),
        "--assessment",
        str(write_json(tmp_path, "assessment.json", make_assessment())),
        "--review",
        str(write_json(tmp_path, "review.json", make_review())),
    ]


def test_cli_write_requires_live(tmp_path):
    code = pr_publish.main([*offline_args(tmp_path), "--write"])

    assert code == 2


def test_cli_write_outside_github_actions_exits_five(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    code = pr_publish.main([*live_args(tmp_path), "--write"])

    assert code == 5


def test_cli_write_inside_actions_without_a_token_exits_four(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    code = pr_publish.main([*live_args(tmp_path), "--write"])

    assert code == 4


def test_cli_write_applies_the_plan_and_prints_the_results(monkeypatch, tmp_path, capsys):
    fake = FakeGitHub(["abc123", "abc123"])
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    code = pr_publish.main([*live_args(tmp_path), "--write"], client=fake)

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == 1
    assert payload["ok"] is True
    assert payload["plan"]["status"] == "planned"
    assert [result["kind"] for result in payload["results"]] == [
        "set_labels",
        "upsert_comment",
        "request_reviewer",
    ]


def test_cli_write_exits_one_when_an_action_failed(monkeypatch, tmp_path, capsys):
    fake = FakeGitHub(["abc123", "abc123"])
    fake.fail_paths.add(COMMENTS_PATH)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    code = pr_publish.main([*live_args(tmp_path), "--write"], client=fake)

    assert code == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert [result["kind"] for result in payload["results"]] == [
        "set_labels",
        "upsert_comment",
        "request_reviewer",
    ]
    failed = [result for result in payload["results"] if not result["ok"]]
    assert [result["kind"] for result in failed] == ["upsert_comment"]
    assert failed[0]["detail"], "a failed action must say what went wrong"


def test_cli_write_prints_an_aborted_plan_when_the_head_changed(monkeypatch, tmp_path, capsys):
    fake = FakeGitHub(["abc123", "def456"])
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    code = pr_publish.main([*live_args(tmp_path), "--write"], client=fake)

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "aborted"
    assert payload["abort_reason"] == "head_sha_changed"
    assert payload["actions"] == []
    assert "results" not in payload
    assert write_calls(fake) == []
