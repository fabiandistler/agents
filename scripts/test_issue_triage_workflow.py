"""Guardrails for the reusable issue triage and its caller.

factory-issue-triage.yml holds the jobs (ADR-0018). Each job holds only the
credential its stage needs: assess reads issues, triage holds the model token
and no GitHub token, publish writes issues and never sees the model token.
Untrusted issue text never reaches a shell. Scripts run from a checkout of the
workflow's own commit outside the workspace the model reads. issue-triage.yml
is a thin caller: triggers, an empty default scope, the scope cap, the secret
by name.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from issue_triage_policy import STATE_LABELS

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "factory-issue-triage.yml"
CALLER = REPO_ROOT / ".github" / "workflows" / "issue-triage.yml"
PR_REVIEW = REPO_ROOT / ".github" / "workflows" / "factory-pr-review.yml"
MODEL_KEY = "CLAUDE_CODE_OAUTH_TOKEN"
UNTRUSTED = re.compile(r"github\.event\.(?:issue\.(?:title|body)|comment\.body)")
FACTORY = "${{ runner.temp }}/factory"
SHA_PINNED = re.compile(r"[\w./-]+@[0-9a-f]{40}")


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _jobs() -> dict:
    return _workflow()["jobs"]


def _caller() -> dict:
    return yaml.safe_load(CALLER.read_text(encoding="utf-8"))


def _caller_job() -> dict:
    jobs = _caller()["jobs"]
    assert list(jobs) == ["triage"], "the caller should have one job"
    return jobs["triage"]


def _is_checkout(step: dict) -> bool:
    return str(step.get("uses", "")).startswith("actions/checkout@")


def _text(job: dict) -> str:
    return yaml.safe_dump(job)


def test_caller_triggers_and_empty_default_permissions():
    caller = _caller()
    # PyYAML reads the bare `on` key as boolean True.
    triggers = caller[True]
    assert triggers["issues"] == {"types": ["opened", "labeled"]}
    assert triggers["issue_comment"] == {"types": ["created"]}
    assert "workflow_dispatch" in triggers
    assert triggers["workflow_dispatch"]["inputs"]["dry_run"]["default"] is True
    assert caller["permissions"] == {}


def test_caller_grants_the_union_of_the_called_scopes_and_nothing_else():
    job = _caller_job()
    assert job["permissions"] == {"contents": "read", "issues": "write"}
    granted = {scope for called in _jobs().values() for scope in called["permissions"]}
    assert granted == set(job["permissions"])


def test_caller_calls_the_reusable_workflow_locally_or_by_sha():
    uses = _caller_job()["uses"]
    assert uses == "./.github/workflows/factory-issue-triage.yml" or (
        SHA_PINNED.fullmatch(uses) and "/factory-issue-triage.yml@" in uses
    ), uses


def test_caller_passes_the_model_token_by_name():
    job = _caller_job()
    assert job["secrets"] == {MODEL_KEY: "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"}, "no `inherit`"


def test_caller_leaves_filter_and_concurrency_to_the_called_workflow():
    # One place only: the called workflow holds the filter and the group.
    job = _caller_job()
    assert "if" not in job
    assert "concurrency" not in job
    assert "concurrency" not in _caller()


def test_caller_passes_the_dispatch_inputs_through():
    passed = _caller_job()["with"]
    assert passed["issue"] == "${{ inputs.issue }}"
    dry_run = " ".join(passed["dry_run"].split())
    assert dry_run == "${{ github.event_name != 'workflow_dispatch' || inputs.dry_run }}"


def test_called_workflow_inputs_and_secret():
    workflow = _workflow()
    assert workflow["permissions"] == {}
    call = workflow[True]["workflow_call"]
    assert set(workflow[True]) == {"workflow_call"}
    inputs = call["inputs"]
    shapes = {name: (spec["type"], spec["default"]) for name, spec in inputs.items()}
    assert shapes == {
        "issue": ("string", ""),
        "dry_run": ("boolean", True),
        "setup_command": ("string", ""),
    }
    assert call["secrets"] == {MODEL_KEY: {"required": True}}


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
                assert SHA_PINNED.fullmatch(uses), f"{name}: {uses}"


def test_the_cli_version_matches_the_pr_review_pin():
    pin = re.compile(r"@anthropic-ai/claude-code@(\S+)")
    triage = pin.findall(WORKFLOW.read_text(encoding="utf-8"))
    review = pin.findall(PR_REVIEW.read_text(encoding="utf-8"))
    assert triage and re.fullmatch(r"\d+\.\d+\.\d+", triage[0]), "pin an exact version"
    assert triage == review, "one Claude Code version for both pipelines"


def test_the_model_reads_the_default_branch_whatever_the_trigger():
    steps = _jobs()["triage"]["steps"]
    workspace = [s for s in steps if _is_checkout(s)]
    assert len(workspace) == 1, "one checkout of the caller into the workspace"
    assert "repository" not in workspace[0]["with"], "the caller's own repository"
    assert workspace[0]["with"]["ref"] == "${{ github.event.repository.default_branch }}"


def test_the_model_reads_the_checkout_and_its_inputs_stay_outside_it():
    run = "\n".join(step.get("run", "") for step in _jobs()["triage"]["steps"])
    assert '--workspace "$GITHUB_WORKSPACE"' in run
    assert '--context "$WORK/context.json"' in run
    assert "runner.temp" in _text(_jobs()["triage"])


def _pr_review_fetch() -> dict:
    review = yaml.safe_load(PR_REVIEW.read_text(encoding="utf-8"))
    return next(
        step
        for job in review["jobs"].values()
        for step in job.get("steps", [])
        if step.get("name") == "Fetch the factory scripts"
    )


def test_every_job_runs_the_scripts_from_the_factory_fetch_outside_the_workspace():
    # One mechanism for every factory task (ADR-0018): the same anonymous fetch
    # of the workflow's own commit into $RUNNER_TEMP/factory as the PR review.
    reference = _pr_review_fetch()
    assert "${{ job.workflow_sha }}" in reference["env"].values()
    for name, job in _jobs().items():
        steps = job["steps"]
        fetches = [s for s in steps if s.get("name") == "Fetch the factory scripts"]
        assert len(fetches) == 1, f"{name}: one factory fetch"
        assert fetches[0]["env"] == reference["env"], name
        assert fetches[0]["run"] == reference["run"], name
        checkouts = [s for s in steps if _is_checkout(s)]
        assert all("repository" not in s["with"] for s in checkouts), name
        for step in steps:
            run = step.get("run", "")
            if "python3" in run:
                assert step["env"]["FACTORY"] == FACTORY, f"{name}: {step.get('name')}"
                assert "scripts/" not in run.replace('"$FACTORY/scripts/', ""), name
        python = [s for s in steps if "python3" in s.get("run", "")]
        assert steps.index(fetches[0]) < steps.index(python[0]), name


def test_the_model_workspace_is_never_the_factory_checkout():
    triage = _jobs()["triage"]
    run = "\n".join(step.get("run", "") for step in triage["steps"])
    assert '--workspace "$GITHUB_WORKSPACE"' in run
    assert not FACTORY.startswith("${{ github.workspace }}")
    assert "$FACTORY" not in run.split("--workspace", 1)[1].split("\n", 1)[0]


def test_the_setup_command_runs_before_the_model_without_secrets():
    steps = _jobs()["triage"]["steps"]
    names = [step.get("name") for step in steps]
    setup = steps[names.index("Run the caller's setup command")]
    assert names.index("Run the caller's setup command") < names.index("Triage the issue")
    assert setup["if"] == "inputs.setup_command != ''"
    assert setup["env"] == {"SETUP_COMMAND": "${{ inputs.setup_command }}"}
    assert "secrets." not in _text(setup)
    assert setup["run"] == 'bash -euo pipefail -c "$SETUP_COMMAND"'


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
    # A run in flight is never cancelled, so it cannot stop between comment and label.
    assert _workflow()["concurrency"]["cancel-in-progress"] is False
    # `a && '' || b` always yields b, so the dropped case must come first.
    assert f"!( {condition} ) && format('-ignored-{{0}}', github.run_id) || ''" in group


def _top_level_clauses(condition: str) -> list[str]:
    """Split an expression at the `||` operators outside any parentheses."""
    clauses, depth, start = [], 0, 0
    for i, char in enumerate(condition):
        depth += {"(": 1, ")": -1}.get(char, 0)
        if depth == 0 and condition.startswith("||", i):
            clauses.append(condition[start:i].strip())
            start = i + 2
    clauses.append(condition[start:].strip())
    return clauses


def _opened_clause() -> str:
    condition = " ".join(_jobs()["assess"]["if"].split())
    opened = [c for c in _top_level_clauses(condition) if "github.event.action == 'opened'" in c]
    assert len(opened) == 1, "the assess `if` should have one `opened` clause"
    return opened[0]


def test_a_new_issue_starts_a_runner_only_without_a_state_label():
    # An issue filed with needs-triage is triaged by its own `labeled` run; one
    # filed with any other state label, or by a bot, would only be told it is
    # not waiting for triage, so it must not start a runner (#797).
    clause = _opened_clause()
    assert "github.event.sender.type != 'Bot'" in clause
    for label in STATE_LABELS:
        assert f"!contains(github.event.issue.labels.*.name, '{label}')" in clause, label


def test_an_issue_filed_with_a_state_label_other_than_needs_triage_is_never_triaged():
    # Through the caller: it filters nothing itself, so the called `opened`
    # clause decides, and the `labeled` clause only passes needs-triage.
    assert "if" not in _caller_job()
    clause = _opened_clause()
    for label in ("needs-info", "ready-for-agent", "ready-for-human", "wontfix"):
        assert f"!contains(github.event.issue.labels.*.name, '{label}')" in clause, label
    condition = " ".join(_jobs()["assess"]["if"].split())
    labeled = [c for c in _top_level_clauses(condition) if "'labeled'" in c]
    expected = (
        "(github.event_name == 'issues' && github.event.action == 'labeled' && "
        "github.event.label.name == 'needs-triage' && github.event.sender.type != 'Bot')"
    )
    assert labeled == [expected]
