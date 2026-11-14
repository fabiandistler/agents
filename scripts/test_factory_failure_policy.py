"""Tests for factory_failure_policy.py: the Fix task's signature and dedupe plan."""

import factory_failure_policy as policy
import pytest

IMPLEMENTER = ".github/workflows/implementer.yml"
FAILURE = {"job": "implement", "step": "Report the run", "reason": "RUN FAILED: claim (HTTP 500)"}
MARKER = policy.signature(IMPLEMENTER, FAILURE["job"], FAILURE["step"], FAILURE["reason"])["marker"]


def _run(**overrides) -> dict:
    run = {
        "id": 111,
        "attempt": 1,
        "path": IMPLEMENTER,
        "name": "implementer",
        "url": "https://github.com/o/r/actions/runs/111",
        "display_title": "implementer: issue #7",
        "conclusion": "failure",
    }
    return {**run, **overrides}


def _issue(number: int, state: str = "open", **overrides) -> dict:
    issue = {
        "number": number,
        "state": state,
        "author": policy.AUTHOR,
        "body": f"{MARKER}\nbody",
        "labels": [policy.LABEL],
        "comments": [],
    }
    return {**issue, **overrides}


def _plan(run=None, open_issue=None, closed_issue=None, fix_issue=None) -> dict:
    return policy.plan(run or _run(), FAILURE, open_issue, closed_issue, fix_issue, "2026-11-13")


# --- signature ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("RUN FAILED: claim (HTTP 500)", "RUN FAILED: claim (HTTP 502)"),
        ("tests red at 3f9c2a1e", "tests red at 0d1e2f3a4b5c6d7e8f90a1b2c3d4e5f6a7b8c9d0"),
        ("see https://x.test/a/1 now", "see http://y.test/b?q=2 now"),
        ("issue #12 blocked", "issue #3401 blocked"),
        ("a  lot\tof   space", "a lot of space"),
    ],
)
def test_reasons_differing_only_in_run_values_share_a_signature(first, second):
    one = policy.signature(IMPLEMENTER, "implement", "Run", first)
    two = policy.signature(IMPLEMENTER, "implement", "Run", second)
    assert one["hash"] == two["hash"]
    assert one["marker"] == f"<!-- factory-failure:{one['hash']} -->"


@pytest.mark.parametrize(
    "changed",
    [
        {"path": ".github/workflows/skill-audit.yml"},
        {"job": "other"},
        {"step": "Claim"},
        {"reason": "RUN FAILED: tests red"},
    ],
)
def test_a_different_workflow_job_step_or_reason_is_another_signature(changed):
    base = {"path": IMPLEMENTER, "job": "implement", "step": "Run", "reason": "RUN FAILED: x"}
    assert policy.signature(**base)["hash"] != policy.signature(**{**base, **changed})["hash"]


def test_the_marker_and_the_run_record_are_distinct_non_empty_comments():
    # Dedupe matches with `in`, so an empty marker or record would match every body.
    sig = policy.signature(IMPLEMENTER, "implement", "Run", "RUN FAILED: x")
    record = policy.run_record({"id": 111, "attempt": 2})
    for marker in (sig["marker"], record):
        assert marker.startswith("<!-- ") and marker.endswith(" -->")
        assert marker[len("<!-- ") : -len(" -->")].strip()
    assert sig["hash"] in sig["marker"]
    assert "111" in record and "2" in record
    assert sig["marker"] not in record and record not in sig["marker"]


def test_plain_hex_words_survive_and_the_reason_is_capped():
    assert policy.normalize_reason("defaced cafebabe") == "defaced cafebabe"
    assert len(policy.normalize_reason("x" * 1000)) == policy.MAX_REASON
    assert policy.normalize_reason("  ") == policy.NO_REASON


def test_the_run_failed_annotation_wins_over_earlier_errors():
    annotations = [
        {"annotation_level": "warning", "message": "Node 20 is deprecated"},
        {"annotation_level": "failure", "message": "Process completed with exit code 1."},
        {"annotation_level": "failure", "message": "RUN FAILED: tests red\nsecond line"},
    ]
    assert policy.failure_reason(annotations) == "RUN FAILED: tests red"
    assert policy.failure_reason(annotations[:2]) == "Process completed with exit code 1."
    assert policy.failure_reason(annotations[:1]) == ""


def test_the_first_failed_job_and_step_are_found():
    jobs = [
        {"id": 1, "name": "assess", "conclusion": "success", "steps": []},
        {
            "id": 2,
            "name": "publish",
            "conclusion": "failure",
            "steps": [
                {"name": "Checkout", "conclusion": "success"},
                {"name": "Publish", "conclusion": "failure"},
                {"name": "Post", "conclusion": "failure"},
            ],
        },
    ]
    assert policy.first_failure(jobs) == {"job": "publish", "step": "Publish", "job_id": 2}
    timed_out = [
        {
            "id": 3,
            "name": "x",
            "conclusion": "failure",
            "steps": [{"name": "Run claude", "conclusion": "cancelled"}],
        }
    ]
    assert policy.first_failure(timed_out)["step"] == "Run claude"
    assert policy.first_failure([])["job"] == policy.UNKNOWN


# --- plan ----------------------------------------------------------------------


def test_no_match_files_a_new_issue_with_marker_labels_and_neutral_reason():
    failure = {**FAILURE, "reason": "RUN FAILED: ping @someone"}
    planned = policy.plan(_run(display_title="other"), failure, None, None, None, "2026-11-13")
    action = planned["action"]
    assert action["kind"] == "create_issue"
    assert action["title"] == "implementer: implement/Report the run failed"
    assert action["labels"] == ["factory-failure", "bug", "needs-triage"]
    assert planned["signature"]["marker"] in action["body"]
    assert "<!-- factory-failure-run:111/1 -->" in action["body"]
    assert "https://github.com/o/r/actions/runs/111" in action["body"]
    assert "```text\nRUN FAILED: ping @\u200bsomeone\n```" in action["body"]
    assert "@someone" not in action["body"]


def test_an_open_match_gets_one_comment():
    planned = _plan(open_issue=_issue(5))
    assert planned["action"]["kind"] == "comment"
    assert planned["action"]["number"] == 5
    body = planned["action"]["body"]
    assert "<!-- factory-failure-run:111/1 -->" in body
    assert "attempt 1" in body and "2026-11-13" in body and "runs/111" in body


@pytest.mark.parametrize("where", ["body", "comment"])
def test_an_already_recorded_run_attempt_writes_nothing(where):
    record = "<!-- factory-failure-run:111/1 -->"
    issue = _issue(5)
    if where == "body":
        issue["body"] += record
    else:
        issue["comments"] = [{"author": policy.AUTHOR, "body": record}]
    planned = _plan(open_issue=issue)
    assert planned["action"] is None
    assert "recorded" in planned["skip_reason"]


def test_a_new_attempt_of_a_recorded_run_still_comments():
    issue = _issue(
        5, comments=[{"author": policy.AUTHOR, "body": "<!-- factory-failure-run:111/1 -->"}]
    )
    assert _plan(run=_run(attempt=2), open_issue=issue)["action"]["kind"] == "comment"


def test_a_record_quoted_by_a_person_does_not_count():
    issue = _issue(
        5, comments=[{"author": "someone", "body": "<!-- factory-failure-run:111/1 -->"}]
    )
    assert _plan(open_issue=issue)["action"]["kind"] == "comment"


def test_only_a_closed_match_files_a_new_issue_naming_it():
    planned = _plan(closed_issue=_issue(4, state="closed"))
    assert planned["action"]["kind"] == "create_issue"
    assert "#4, now closed" in planned["action"]["body"]


def test_find_issues_takes_only_bot_issues_with_the_marker():
    issues = [
        _issue(1, state="closed"),
        _issue(3, state="closed"),
        _issue(6, author="someone"),
        _issue(7, body="no marker"),
        _issue(8),
    ]
    open_issue, closed = policy.find_issues(issues, MARKER)
    assert open_issue is not None and open_issue["number"] == 8
    assert closed is not None and closed["number"] == 3
    assert policy.find_issues(issues[2:4], MARKER) == (None, None)


@pytest.mark.parametrize("conclusion", ["success", "cancelled", "skipped", "neutral", None])
def test_other_conclusions_are_ignored(conclusion):
    planned = _plan(run=_run(conclusion=conclusion))
    assert planned["action"] is None
    assert "not failure or timed_out" in planned["skip_reason"]


def test_a_timed_out_run_is_filed():
    assert _plan(run=_run(conclusion="timed_out"))["action"]["kind"] == "create_issue"


@pytest.mark.parametrize("path", [".github/workflows/ci.yml", ".github/workflows/fix-task.yml", ""])
def test_an_unwatched_workflow_is_ignored(path):
    planned = _plan(run=_run(path=path))
    assert planned["action"] is None
    assert planned["skip_reason"] == "the workflow is not watched"


def test_a_fix_related_implementer_run_comments_on_the_failure_issue_it_works():
    fix_issue = _issue(7, body="another failure", comments=[])
    planned = _plan(open_issue=None, fix_issue=fix_issue)
    assert planned["action"]["kind"] == "comment"
    assert planned["action"]["number"] == 7


def test_a_fix_related_run_wins_over_an_open_signature_match():
    planned = _plan(open_issue=_issue(5), fix_issue=_issue(7, body="x"))
    assert planned["action"]["number"] == 7


def test_an_implementer_run_on_an_ordinary_issue_files_normally():
    fix_issue = _issue(7, labels=["enhancement"], body="x")
    assert _plan(fix_issue=fix_issue)["action"]["kind"] == "create_issue"


@pytest.mark.parametrize(
    ("run", "expected"),
    [
        (_run(), 7),
        (_run(display_title="Fix #7: something"), None),
        (_run(display_title="implementer: issue #7 extra"), None),
        (_run(path=".github/workflows/skill-audit.yml"), None),
    ],
)
def test_only_the_implementer_run_name_names_the_fix_issue(run, expected):
    assert policy.fix_issue_number(run) == expected
