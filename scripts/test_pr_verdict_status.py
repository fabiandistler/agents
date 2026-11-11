"""Tests for the `pr-review/verdict` commit status of the PR review pipeline.

The status lets a ruleset make a merge wait for the review without making the
review a gate: any verdict is green. These tests cover the planned state
(pr_verdict_status.py, pr_plan.py), what the writer may send (pr_actions.py,
pr_apply.py) and the publish paths that must not write it (dry run, stale
head, failed publish). None touches the network.
"""

from __future__ import annotations

import pr_actions
import pr_apply
import pr_github_client
import pr_plan
import pr_publish
import pr_summary
import pr_verdict_status
import pytest
from pr_apply_testkit import FakeClient, make_plan, only_result
from pr_publish_testkit import (
    NUMBER,
    REPO,
    FakeGitHub,
    actions_of,
    live_args,
    make_assessment,
    make_context,
    make_review,
    write_calls,
)

HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"
STATUS_PATH = f"/repos/{REPO}/statuses/{HEAD_SHA}"
RUN_URL = "https://github.com/fabiandistler/agents/actions/runs/123"


def status_of(plan: dict) -> dict:
    [action] = actions_of(plan, "set_status")
    return action


def plan_for(review: dict, *, draft: bool = False, fork: bool = False) -> dict:
    return pr_plan.plan_publish(
        make_context(head_sha=HEAD_SHA, draft=draft, fork=fork),
        make_assessment(head_sha=HEAD_SHA),
        {**review, "head_sha": HEAD_SHA},
    )


def status_action(**overrides: object) -> dict:
    action = {
        "kind": "set_status",
        "sha": HEAD_SHA,
        "context": pr_verdict_status.CONTEXT,
        "state": "success",
        "description": "Verdict: pass. Advisory; read the review comment.",
        "target_url": None,
    }
    action.update(overrides)
    return action


# --- Planned state -----------------------------------------------------------


@pytest.mark.parametrize("verdict", ["pass", "concerns", "block"])
def test_any_verdict_turns_the_status_green(verdict):
    action = status_of(plan_for(make_review(verdict=verdict, risk="high")))

    assert action["state"] == "success", "the review is advisory: no verdict may hold a merge"
    assert action["description"].startswith(f"Verdict: {verdict}")
    assert action["context"] == "pr-review/verdict"


def test_a_partial_review_says_so_in_the_status():
    action = status_of(plan_for(make_review(partial=True)))

    assert action["state"] == "success"
    assert "partial review" in action["description"]


def test_an_unavailable_review_is_no_verdict():
    review = make_review(status="unavailable", verdict=None, risk="high")

    action = status_of(plan_for(review))

    assert action["state"] == "error", "a failed review must not let the merge go ahead"
    assert "Re-run pr-review" in action["description"]


def test_a_draft_waits_for_the_ready_for_review_run():
    review = make_review(status="skipped", verdict=None, risk=None)

    action = status_of(plan_for(review, draft=True))

    assert action["state"] == "pending"
    assert action["description"].startswith("Draft:")


def test_a_fork_is_final_without_a_model_review():
    review = make_review(status="skipped", verdict=None, risk=None)

    action = status_of(plan_for(review, fork=True))

    assert action["state"] == "success", "a fork is never reviewed; it must not stay blocked"
    assert action["description"].startswith("Fork:")


def test_a_draft_fork_still_waits_until_it_is_ready():
    review = make_review(status="skipped", verdict=None, risk=None)

    assert status_of(plan_for(review, draft=True, fork=True))["state"] == "pending"


def test_every_description_fits_the_writer_limit():
    descriptions = [
        pr_verdict_status.UNAVAILABLE,
        pr_verdict_status.DRAFT,
        pr_verdict_status.FORK,
        status_of(plan_for(make_review(verdict="concerns", partial=True)))["description"],
    ]

    assert all(len(text) <= pr_verdict_status.MAX_DESCRIPTION for text in descriptions)


def test_the_status_is_the_last_action_and_pinned_to_the_assessed_head():
    plan = pr_plan.plan_publish(
        make_context(head_sha=HEAD_SHA),
        make_assessment(head_sha=HEAD_SHA),
        make_review(head_sha=HEAD_SHA),
        auto_merge=True,
        status_url=RUN_URL,
    )

    assert plan["actions"][-1] == status_action(target_url=RUN_URL)
    assert plan["decision"]["verdict_status"] == "success"


@pytest.mark.parametrize(
    ("context", "reason"),
    [
        ({"head_sha": "fedcba9876543210fedcba9876543210fedcba98"}, "head_sha_changed"),
        ({"head_sha": HEAD_SHA, "state": "closed"}, "pull_request_closed"),
    ],
)
def test_an_aborted_plan_sets_no_status(context, reason):
    plan = pr_plan.plan_publish(
        make_context(**context),
        make_assessment(head_sha=HEAD_SHA),
        make_review(head_sha=HEAD_SHA),
    )

    assert plan["abort_reason"] == reason
    assert actions_of(plan, "set_status") == []
    assert plan["decision"]["verdict_status"] is None


def test_the_hold_never_sets_a_status():
    plan = pr_plan.plan_hold(make_context(head_sha=HEAD_SHA))

    assert actions_of(plan, "set_status") == []


# --- What the writer sends ---------------------------------------------------


def test_the_status_resolves_to_one_commit_status_post():
    client = FakeClient()

    result = only_result(
        pr_apply.apply_plan(make_plan([status_action()], head_sha=HEAD_SHA), client)
    )

    assert result == {
        "kind": "set_status",
        "ok": True,
        "detail": "set pr-review/verdict to success",
    }
    [call] = client.calls
    assert (call["method"], call["path"]) == ("POST", STATUS_PATH)
    assert call["payload"] == {
        "state": "success",
        "context": "pr-review/verdict",
        "description": "Verdict: pass. Advisory; read the review comment.",
    }


def test_the_run_url_becomes_the_status_link():
    client = FakeClient()
    plan = make_plan([status_action(target_url=RUN_URL)], head_sha=HEAD_SHA)

    pr_apply.apply_plan(plan, client)

    assert client.calls[0]["payload"]["target_url"] == RUN_URL


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"context": "checks"}, "may only set the context pr-review/verdict"),
        ({"sha": "fedcba9876543210fedcba9876543210fedcba98"}, "head commit the plan assessed"),
        ({"sha": "../../pulls/42"}, "commit SHA"),
        ({"state": "failure"}, "accepts only the states"),
        ({"state": "bogus"}, "accepts only the states"),
        ({"description": ""}, "description"),
        ({"description": "x" * 141}, "at most 140 characters"),
        ({"target_url": "http://example.test/run"}, "https URL"),
    ],
)
def test_the_writer_refuses_any_other_status(override, message):
    client = FakeClient()
    plan = make_plan([status_action(**override)], head_sha=HEAD_SHA)

    with pytest.raises(pr_actions.PlanError, match=message):
        pr_apply.apply_plan(plan, client)
    assert client.calls == [], "a refused plan must not half-apply"


def _fail_labels(method: str, path: str, payload: dict | None):
    if path.endswith("/labels"):
        return pr_github_client.FetchError("server error", status=500)
    return pr_github_client.Response(status=201, body=b"{}")


def test_a_failed_earlier_action_withholds_a_green_status():
    client = FakeClient(handler=_fail_labels)
    plan = make_plan(
        [{"kind": "set_labels", "add": ["risk:low"], "remove": []}, status_action()],
        head_sha=HEAD_SHA,
    )

    results = pr_apply.apply_plan(plan, client)

    assert [result["ok"] for result in results] == [False, False]
    assert results[1]["detail"].startswith("not set")
    assert not any("/statuses/" in call["path"] for call in client.calls)


@pytest.mark.parametrize("state", ["pending", "error"])
def test_a_status_that_holds_the_merge_is_sent_even_after_a_failure(state):
    client = FakeClient(handler=_fail_labels)
    plan = make_plan(
        [
            {"kind": "set_labels", "add": ["risk:low"], "remove": []},
            status_action(state=state, description="Waiting."),
        ],
        head_sha=HEAD_SHA,
    )

    results = pr_apply.apply_plan(plan, client)

    assert results[1]["ok"] is True
    assert ("POST", STATUS_PATH) in [(call["method"], call["path"]) for call in client.calls]


# --- Publish paths -----------------------------------------------------------


def test_a_dry_run_plans_the_status_but_writes_nothing():
    fake = FakeGitHub([HEAD_SHA])

    plan = pr_publish.publish_live(
        REPO,
        NUMBER,
        make_assessment(head_sha=HEAD_SHA),
        make_review(head_sha=HEAD_SHA),
        client=fake,
        status_url=RUN_URL,
    )

    assert status_of(plan)["state"] == "success"
    assert write_calls(fake) == []


def test_a_head_pushed_during_the_run_gets_no_status_from_it():
    fake = FakeGitHub([HEAD_SHA, "fedcba9876543210fedcba9876543210fedcba98"])

    payload = pr_publish.publish_live(
        REPO,
        NUMBER,
        make_assessment(head_sha=HEAD_SHA),
        make_review(head_sha=HEAD_SHA),
        write=True,
        client=fake,
    )

    assert payload["status"] == "aborted"
    assert write_calls(fake) == []


def test_a_write_sets_the_status_on_the_reviewed_head_last():
    fake = FakeGitHub([HEAD_SHA, HEAD_SHA])

    pr_publish.publish_live(
        REPO,
        NUMBER,
        make_assessment(head_sha=HEAD_SHA),
        make_review(head_sha=HEAD_SHA),
        write=True,
        client=fake,
        status_url=RUN_URL,
    )

    last = write_calls(fake)[-1]
    assert last["path"] == STATUS_PATH
    assert last["payload"]["state"] == "success"
    assert last["payload"]["target_url"] == RUN_URL


def test_the_cli_passes_the_status_url_through(monkeypatch, tmp_path, capsys):
    fake = FakeGitHub(["abc1234"])

    code = pr_publish.main([*live_args(tmp_path), "--status-url", RUN_URL], client=fake)

    assert code == 0
    assert RUN_URL in capsys.readouterr().out


@pytest.mark.parametrize(
    "arguments",
    [
        ["--status-url", "http://example.test/run"],
        ["--hold", "--status-url", RUN_URL],
    ],
)
def test_the_cli_refuses_a_bad_status_url(tmp_path, capsys, arguments):
    base = ["--live", "--repo", REPO, "--pr", str(NUMBER)]
    if "--hold" not in arguments:
        base = live_args(tmp_path)

    assert pr_publish.main([*base, *arguments]) == 2
    assert "--status-url" in capsys.readouterr().err


def test_the_summary_names_the_verdict_status():
    plan = pr_plan.plan_publish(make_context(), make_assessment(), make_review())

    assert "- pr-review/verdict: success" in pr_summary.render_summary(plan, make_review())
