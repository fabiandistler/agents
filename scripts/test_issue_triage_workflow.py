"""Guardrails for .github/workflows/issue-triage.yml.

Each job holds only the credential its stage needs: assess reads issues,
triage holds the model token and no GitHub token, publish writes issues and
never sees the model token. Untrusted issue text never reaches a shell.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "issue-triage.yml"
PR_REVIEW = REPO_ROOT / ".github" / "workflows" / "pr-review.yml"
MODEL_KEY = "CLAUDE_CODE_OAUTH_TOKEN"
UNTRUSTED = re.compile(r"github\.event\.(?:issue\.(?:title|body)|comment\.body)")


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _jobs() -> dict:
    return _workflow()["jobs"]


def _text(job: dict) -> str:
    return yaml.safe_dump(job)


def test_triggers_and_empty_default_permissions():
    workflow = _workflow()
    # PyYAML reads the bare `on` key as boolean True.
    triggers = workflow[True]
    assert triggers["issues"] == {"types": ["opened", "labeled"]}
    assert triggers["issue_comment"] == {"types": ["created"]}
    assert "workflow_dispatch" in triggers
    assert triggers["workflow_dispatch"]["inputs"]["dry_run"]["default"] is True
    assert workflow["permissions"] == {}


def test_each_job_has_exactly_its_own_scope():
    jobs = _jobs()
    assert list(jobs) == ["assess", "triage", "publish"]
    assert jobs["assess"]["permissions"] == {"issues": "read"}
    assert jobs["triage"]["permissions"] == {"contents": "read"}
    assert jobs["publish"]["permissions"] == {"issues": "write"}


def test_only_the_triage_job_holds_the_model_token_and_it_holds_no_github_token():
    jobs = _jobs()
    assert MODEL_KEY in _text(jobs["triage"])
    assert "GITHUB_TOKEN" not in _text(jobs["triage"])
    assert "github.token" not in _text(jobs["triage"])
    for name in ("assess", "publish"):
        assert MODEL_KEY not in _text(jobs[name]), f"{name} must not see the model token"


def test_every_checkout_drops_its_credentials():
    for name, job in _jobs().items():
        for step in job["steps"]:
            if str(step.get("uses", "")).startswith("actions/checkout@"):
                assert step["with"]["persist-credentials"] is False, name


def test_untrusted_issue_text_never_reaches_a_run_step():
    for name, job in _jobs().items():
        for step in job["steps"]:
            run = step.get("run", "")
            assert "${{" not in run, f"{name}: pass event values through env"
            env = yaml.safe_dump(step.get("env", {}))
            assert not UNTRUSTED.search(env), f"{name}: issue text must not enter env"


def test_actions_are_pinned_to_a_commit():
    for name, job in _jobs().items():
        for step in job["steps"]:
            uses = step.get("uses")
            if uses:
                assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", uses), f"{name}: {uses}"


def test_the_cli_version_matches_the_pr_review_pin():
    pin = re.compile(r"@anthropic-ai/claude-code@(\S+)")
    triage = pin.findall(WORKFLOW.read_text(encoding="utf-8"))
    review = pin.findall(PR_REVIEW.read_text(encoding="utf-8"))
    assert triage and re.fullmatch(r"\d+\.\d+\.\d+", triage[0]), "pin an exact version"
    assert triage == review, "one Claude Code version for both pipelines"


def test_the_model_reads_the_checkout_and_its_inputs_stay_outside_it():
    run = "\n".join(step.get("run", "") for step in _jobs()["triage"]["steps"])
    assert '--workspace "$GITHUB_WORKSPACE"' in run
    assert '--context "$WORK/context.json"' in run
    assert "runner.temp" in _text(_jobs()["triage"])


def test_publish_runs_for_a_requeue_even_when_the_triage_was_skipped():
    condition = " ".join(_jobs()["publish"]["if"].split())
    assert condition.startswith("always() && needs.assess.result == 'success'")
    assert "needs.assess.outputs.requeue == 'true'" in condition
    assert "needs.assess.outputs.eligible == 'true'" in condition


def test_a_manual_run_writes_only_when_dry_run_is_off():
    steps = _jobs()["publish"]["steps"]
    publish = next(step for step in steps if step.get("name") == "Publish the triage")
    write = " ".join(publish["env"]["WRITE"].split())
    assert write == "${{ github.event_name != 'workflow_dispatch' || inputs.dry_run == false }}"


def test_only_the_reporter_reply_on_a_needs_info_issue_starts_a_run():
    condition = " ".join(_jobs()["assess"]["if"].split())
    assert "github.event.comment.user.login == github.event.issue.user.login" in condition
    assert "contains(github.event.issue.labels.*.name, 'needs-info')" in condition
    assert "!github.event.issue.pull_request" in condition
    assert "github.event.label.name == 'needs-triage'" in condition


def test_events_the_filter_drops_never_share_the_triage_concurrency_group():
    group = " ".join(_workflow()["concurrency"]["group"].split())
    condition = " ".join(_jobs()["assess"]["if"].split())
    assert _workflow()["concurrency"]["cancel-in-progress"] is True
    # `a && '' || b` always yields b, so the dropped case must come first.
    assert f"!( {condition} ) && format('-ignored-{{0}}', github.run_id) || ''" in group
