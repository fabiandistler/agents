"""The merged-PR gate, Markdown section boundaries and idempotent issue writes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from hand_part_follow_up import (
    EXIT_FAILED,
    EXIT_USAGE,
    main,
    plan_follow_ups,
    publish_follow_ups,
)
from pr_github_client import FetchError
from pr_github_fake import json_response

REPO = "fabiandistler/agents"
ISSUES = f"/repos/{REPO}/issues"
COMMENTS = f"{ISSUES}/954/comments"
SHA = "a" * 40
SECTION = (
    "## Hook config to add by hand\n\n```yaml\nkey: value\n```\n\n### Verify\nRun the checks.\n"
)


def merge_event(body=f"Closes #954\n\n{SECTION}", **overrides):
    return {
        "action": "closed",
        "pull_request": {
            "number": 966,
            "merged": True,
            "body": body,
            "user": {"login": "claude[bot]", "type": "Bot"},
            "head": {"ref": "agent/issue-954", "repo": {"full_name": REPO}},
            "merge_commit_sha": SHA,
            **overrides,
        },
    }


def bot_entry(payload):
    return {**payload, "user": {"login": "github-actions[bot]"}}


class GitHub:
    def __init__(self):
        self.issues = []
        self.comments = []
        self.posts = []
        self.fail_comment = False

    def get(self, path, params: dict[str, object] | None = None, accept=None):
        if path == ISSUES:
            assert params is not None and params["state"] == "all"
            return json_response(self.issues)
        assert path == COMMENTS
        return json_response(self.comments)

    def post(self, path, payload):
        if path == ISSUES:
            number = 1000 + len(self.issues)
            self.issues.append(bot_entry({**payload, "number": number}))
            self.posts.append(path)
            return json_response({"number": number}, 201)
        assert path == COMMENTS
        if self.fail_comment:
            raise FetchError("comment request failed")
        self.comments.append(bot_entry(payload))
        self.posts.append(path)
        return json_response({}, 201)


def test_creates_labeled_issue_with_verbatim_section_and_one_link_comment():
    event = merge_event(
        f"Closes #954\r\n\r\n{SECTION.replace(chr(10), chr(13) + chr(10))}## Other\n"
    )
    plan = plan_follow_ups(event, REPO)
    assert plan is not None
    github = GitHub()

    assert publish_follow_ups(github, REPO, plan) == [1000]

    [issue] = github.issues
    assert issue["title"] == "Apply by hand: Hook config to add by hand from #966"
    assert issue["labels"] == ["ready-for-human"]
    assert issue["body"] == (
        f"<!-- hand-part:966/1 -->\n\nHand-applied work from PR #966 for issue #954 "
        f"(merge commit `{SHA}`).\n\n" + SECTION.replace("\n", "\r\n")
    )
    assert [comment["body"] for comment in github.comments] == [
        "<!-- hand-part:966/1 -->\n\nTracked the hand-applied work in #1000."
    ]


def test_two_sections_with_identical_titles_get_distinct_issues():
    plan = plan_follow_ups(merge_event(f"Closes #954\n\n{SECTION}\n{SECTION}"), REPO)
    assert plan is not None
    github = GitHub()

    assert publish_follow_ups(github, REPO, plan) == [1000, 1001]
    assert github.posts == [ISSUES, COMMENTS, ISSUES, COMMENTS]
    assert github.issues[1]["body"].startswith("<!-- hand-part:966/2 -->\n")


def test_headings_inside_a_fence_quote_or_comment_do_not_count():
    body = (
        "Closes #954\n\n"
        "> ## Quoted config to add by hand\n"
        "<!--\n## Hidden config to add by hand\n-->\n"
        "````markdown\n"
        "```\n"
        "````not-closed\n"
        "## Fenced config to add by hand\n"
        "````\n\n"
        "~~~\n## Another fenced config to add by hand\n~~~\n\n"
        "- ```markdown\n  ## Nested fence to add by hand\n  ```\n\n"
        f"{SECTION}"
    )
    plan = plan_follow_ups(merge_event(body), REPO)
    assert plan is not None
    assert [item.title for item in plan.follow_ups] == [
        "Apply by hand: Hook config to add by hand from #966"
    ]


def test_rerun_writes_nothing_even_after_the_follow_up_is_closed():
    plan = plan_follow_ups(merge_event(), REPO)
    assert plan is not None
    github = GitHub()
    publish_follow_ups(github, REPO, plan)
    github.issues[0].update(state="closed", labels=[])
    github.posts.clear()

    assert publish_follow_ups(github, REPO, plan) == []
    assert github.posts == []


def test_retry_restores_a_missing_comment_then_creates_remaining_issues():
    plan = plan_follow_ups(
        merge_event(f"Closes #954\n\n{SECTION}\n## Workflow to add by hand\nDetails.\n"),
        REPO,
    )
    assert plan is not None
    github = GitHub()
    github.fail_comment = True
    with pytest.raises(FetchError, match="comment request failed"):
        publish_follow_ups(github, REPO, plan)

    github.posts.clear()
    github.fail_comment = False
    assert publish_follow_ups(github, REPO, plan) == [1001]
    assert github.posts == [COMMENTS, ISSUES, COMMENTS]
    assert [comment["body"].splitlines()[-1] for comment in github.comments] == [
        "Tracked the hand-applied work in #1000.",
        "Tracked the hand-applied work in #1001.",
    ]


def test_only_the_leading_marker_on_bot_authored_entries_counts():
    plan = plan_follow_ups(merge_event(), REPO)
    assert plan is not None
    github = GitHub()
    user_entry = {"body": "<!-- hand-part:966/1 -->\n", "user": {"login": "human"}}
    copied_marker = bot_entry({"body": "Quoted marker\n\n<!-- hand-part:966/1 -->\n"})
    github.issues[:] = [{**user_entry, "number": 995}, {**copied_marker, "number": 996}]
    github.comments[:] = [user_entry, copied_marker]

    assert publish_follow_ups(github, REPO, plan) == [1002]
    assert github.posts == [ISSUES, COMMENTS]


@pytest.mark.parametrize(
    "overrides",
    [
        {"merged": False},
        {"user": {"login": "maintainer", "type": "User"}},
        {"head": {"ref": "feature", "repo": {"full_name": REPO}}},
        {"head": {"ref": "agent/issue-954", "repo": {"full_name": "fork/agents"}}},
        {"head": {"ref": "agent/issue-999", "repo": {"full_name": REPO}}},
        {"body": "Closes #954\n\n## Changes\nDetails."},
    ],
)
def test_prs_outside_the_merged_implementer_gate_write_nothing(overrides):
    assert plan_follow_ups(merge_event(**overrides), REPO) is None


def test_dry_run_prints_the_plan_without_any_github_calls(tmp_path, capsys):
    event_path = tmp_path / "merge.json"
    event_path.write_text(json.dumps(merge_event()), encoding="utf-8")
    client = GitHub()
    args = ["--repo", REPO, "--event", str(event_path), "--dry-run"]

    assert main(args, client) == 0
    assert json.loads(capsys.readouterr().out) == {
        "titles": ["Apply by hand: Hook config to add by hand from #966"]
    }
    assert client.posts == []


def test_workflow_uses_only_closed_events_and_the_trusted_default_branch():
    path = Path(__file__).resolve().parents[1] / ".github/workflows/hand-part-follow-up.yml"
    source = path.read_text(encoding="utf-8")
    workflow = yaml.safe_load(source)
    job = workflow["jobs"]["file-follow-up"]
    assert workflow[True] == {"pull_request": {"types": ["closed"]}}
    assert workflow["permissions"] == {}
    assert "github.event.pull_request.merged" in job["if"]
    assert job["permissions"] == {"contents": "read", "issues": "write"}
    assert job["concurrency"]["group"].endswith("${{ github.event.pull_request.number }}")
    assert job["concurrency"]["cancel-in-progress"] is False
    assert job["steps"][0]["with"] == {
        "ref": "${{ github.event.repository.default_branch }}",
        "persist-credentials": False,
    }
    assert "${{ github.event.pull_request" not in job["steps"][-1]["run"]


def test_an_event_that_is_no_json_object_names_the_flag(tmp_path, assert_exit_cause):
    event_path = tmp_path / "merge.json"
    event_path.write_text("[]", encoding="utf-8")

    exit_code = main(["--repo", REPO, "--event", str(event_path)], GitHub())

    stdout, stderr = assert_exit_cause(exit_code, EXIT_FAILED)
    assert "--event must contain a JSON object" in stderr
    assert stdout == ""


def test_a_missing_flag_is_a_usage_error(assert_exit_cause):
    with pytest.raises(SystemExit) as usage_exit:
        main(["--event", "merge.json"])

    _, stderr = assert_exit_cause(usage_exit.value.code, EXIT_USAGE)
    assert "--repo" in stderr
