"""Tests for the linked-issue section of the review payload (scripts/pr_review.py)."""

from __future__ import annotations

import json

import pr_review
import pr_review_claude
import pr_review_linked_issues as linked
import pr_risk
import pytest
from pr_review_testkit import base_context, run_cli, user_payload, write_context
from pr_risk_testkit import make_context

END_OF_DIFF = "=== END OF DIFF ==="
TOTAL_NOTE = "[Input truncated to the total review limit.]"


def issue(number: int, title: str = "", body: str = "", status: str = "ok") -> dict:
    return {
        "number": number,
        "status": status,
        "title": title if status != "ok" or title else f"Issue {number}",
        "body": body if status != "ok" or body else f"Body of issue {number}",
    }


def build(**overrides: object) -> tuple[dict, bool]:
    return pr_review.build_request(base_context(**overrides))


def test_a_linked_issue_appears_after_the_diff_between_its_markers():
    request, partial = build(linked_issues=[issue(7, "Add the flag", "The ticket text.")])

    payload = user_payload(request)
    after_diff = payload.split(END_OF_DIFF, 1)[1]
    assert after_diff == (
        "\n\n"
        f"{linked.LINKED_ISSUES_HEADER}\n"
        "=== issue #7 ===\n"
        "TITLE: Add the flag\n"
        "BODY:\n"
        "The ticket text.\n"
        "=== end issue #7 ===\n"
    )
    assert partial is False


@pytest.mark.parametrize("field", [{}, {"linked_issues": []}])
def test_no_linked_issue_leaves_the_request_identical(field):
    plain, plain_partial = build()
    request, partial = build(**field)

    assert request == plain
    assert partial is plain_partial
    assert "LINKED ISSUES" not in user_payload(request)


def test_the_system_prompt_is_the_same_with_linked_issues():
    plain, _ = build()
    request, _ = build(linked_issues=[issue(7)])

    assert request["messages"][0] == plain["messages"][0]


def test_unavailable_and_outside_author_issues_render_without_text():
    request, partial = build(
        linked_issues=[issue(3, status="unavailable"), issue(4, status="outside_author")]
    )

    payload = user_payload(request)
    assert "=== issue #3 ===\n(issue #3 could not be fetched)\n=== end issue #3 ===" in payload
    assert (
        "=== issue #4 ===\n(issue #4 is not shown: outside author)\n=== end issue #4 ===" in payload
    )
    assert partial is False


def test_issue_text_is_sanitized_without_marking_the_review_partial():
    body = "Visible <!-- HIDDEN-COMMENT --> text\u200b here"
    request, partial = build(linked_issues=[issue(7, "Title <!-- HIDDEN-TITLE -->", body)])

    payload = user_payload(request)
    assert "HIDDEN-" not in payload
    assert "\u200b" not in payload
    assert "Visible" in payload
    assert partial is False


def test_issue_title_and_body_are_capped_without_marking_the_review_partial():
    title = "T" * 2000
    body = "\n".join("b" * 99 for _ in range(400))  # 40,000 bytes
    request, partial = build(linked_issues=[issue(7, title, body)])

    section = user_payload(request).split(END_OF_DIFF, 1)[1]
    title_line = next(line for line in section.splitlines() if line.startswith("TITLE: "))
    assert len(title_line.removeprefix("TITLE: ").encode("utf-8")) <= linked.MAX_ISSUE_TITLE_BYTES
    body_text = section.split("BODY:\n", 1)[1].split(linked.ISSUE_TRUNCATED, 1)[0]
    assert len(body_text.encode("utf-8")) <= linked.MAX_ISSUE_BODY_BYTES + 1
    assert f"{linked.ISSUE_TRUNCATED}\n=== end issue #7 ===" in section
    assert partial is False
    assert pr_review.TRUNCATION_NOTE not in user_payload(request)


def test_issues_beyond_the_room_left_never_displace_the_diff_or_set_partial():
    # A diff that fits the caps, then three capped issues that exceed what is
    # left of the total budget.
    diff = "\n".join(f"+line {n:04d} " + "~" * 90 for n in range(1900)) + "\n"
    base_files = {f"docs/file-{n:02d}.md": "y " * 2_450 for n in range(20)}
    issues = [issue(n, body="\n".join("b" * 99 for _ in range(200))) for n in (1, 2, 3)]
    context = base_context(diff=diff, base_files=base_files, linked_issues=issues)
    plain, plain_partial = pr_review.build_request(base_context(diff=diff, base_files=base_files))
    request, partial = pr_review.build_request(context)

    assert plain_partial is False
    assert partial is False
    payload = user_payload(request)
    assert payload.startswith(user_payload(plain))
    assert "+line 1899" in payload
    assert TOTAL_NOTE not in payload
    assert pr_review.TRUNCATION_NOTE not in payload
    budget = pr_review.MAX_TOTAL_BYTES - len(request["messages"][0]["content"].encode("utf-8"))
    assert len(payload.encode("utf-8")) <= budget
    assert len(payload.encode("utf-8")) > budget - 200  # the room left is used, not dropped
    assert linked.ISSUE_TRUNCATED in payload


def test_a_payload_cut_by_the_total_limit_leaves_no_room_for_issues():
    context = base_context(
        diff="\n".join("~" * 100 for _ in range(2000)),
        base_files={f"docs/file-{n}.md": "y " * 2500 for n in range(20)},
        body="B " * 1000,
        linked_issues=[issue(7, body="ISSUE-BODY")],
    )
    request, partial = pr_review.build_request(context)

    assert partial is True
    assert "ISSUE-BODY" not in user_payload(request)
    assert len(user_payload(request).encode("utf-8")) <= pr_review.MAX_TOTAL_BYTES


def test_issue_text_reaches_the_user_message_only():
    canary = "CANARY-7f3e-issue-body"
    request, _ = build(linked_issues=[issue(7, f"title {canary}", f"body {canary}")])

    assert canary in user_payload(request)
    assert canary not in request["messages"][0]["content"]
    assert not any(canary in argument for argument in pr_review_claude.claude_command(request))


@pytest.mark.parametrize(
    "linked_issues",
    [
        "Closes #7",
        [7],
        [{"number": 0, "status": "ok", "title": "", "body": ""}],
        [{"number": True, "status": "ok", "title": "", "body": ""}],
        [{"number": "7", "status": "ok", "title": "", "body": ""}],
        [{"number": 7, "status": "maybe", "title": "", "body": ""}],
        [{"number": 7, "status": "ok", "title": None, "body": ""}],
        [{"number": 7, "status": "ok", "title": ""}],
    ],
)
def test_a_malformed_linked_issues_field_is_rejected_with_exit_three(tmp_path, linked_issues):
    with pytest.raises(pr_review.ContextError):
        pr_review.build_request(base_context(linked_issues=linked_issues))
    run = run_cli(
        "--context",
        str(write_context(tmp_path, base_context(linked_issues=linked_issues))),
        "--dry-run",
    )
    assert run.returncode == 3
    assert "linked_issues" in run.stderr


def test_the_risk_assessment_ignores_the_field():
    context = make_context()
    with_issues = json.loads(json.dumps({**context, "linked_issues": [issue(7)]}))

    assert pr_risk.classify_pull_request(with_issues) == pr_risk.classify_pull_request(context)
