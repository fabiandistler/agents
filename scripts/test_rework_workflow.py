"""Guardrails for rework.yml, the Rework task (ADR-0015).

The model-free gate writes with GITHUB_TOKEN; the model job runs
claude-code-action with the Claude GitHub App token. These tests pin what keeps
that safe: empty top-level permissions, narrow job scopes, a SHA-pinned action,
no `github_token` override, no event text in the prompt, findings handed over
as a file artifact, and the report step.
"""

import re
from pathlib import Path
from typing import cast

import rework_gate
import yaml
from pr_github_client import GitHubClient
from rework_testkit import (
    OTHER_HEAD,
    OWN_RUN,
    PR,
    REPO,
    REVIEW_RUN,
    THIRD_HEAD,
    FakeGitHub,
    context,
    marker,
    rest_comment,
    review,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "rework.yml"

ACTION = "anthropics/claude-code-action@"
SHA_PIN = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")
EXPRESSION = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")
PROMPT_EXPRESSIONS = {
    "steps.gate.outputs.pr",
    "steps.gate.outputs.issue",
    "steps.gate.outputs.round",
    "github.repository",
}


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _job(name: str) -> dict:
    return _workflow()["jobs"][name]


def _model_step() -> dict:
    steps = [step for step in _job("rework")["steps"] if step.get("uses", "").startswith(ACTION)]
    assert len(steps) == 1, "exactly one claude-code-action step"
    return steps[0]


def test_triggers_on_a_completed_review_or_a_manual_run_never_a_label():
    triggers = _workflow()[True]
    assert triggers["workflow_run"] == {"workflows": ["pr-review"], "types": ["completed"]}
    assert triggers["workflow_dispatch"]["inputs"]["pr"]["required"] is True
    assert set(triggers) == {"workflow_run", "workflow_dispatch"}


def test_permissions_are_empty_by_default_and_narrow_in_each_job():
    assert _workflow()["permissions"] == {}
    assert _job("gate")["permissions"] == {
        "contents": "read",
        "actions": "read",
        "pull-requests": "write",
        "issues": "write",
    }
    assert _job("rework")["permissions"] == {"contents": "read", "id-token": "write"}


def _gate_write_paths(tmp_path: Path, comments: list[dict]) -> set[str]:
    fake = FakeGitHub(comments=comments)
    rework_gate.decide_rework(
        cast(GitHubClient, fake),
        REPO,
        REVIEW_RUN,
        review(),
        context(),
        own_run_id=OWN_RUN,
        findings_path=tmp_path / "findings.json",
        write=True,
    )
    return {path for _, path, _ in fake.writes}


def test_the_gate_holds_write_scope_on_every_kind_of_target_it_writes(tmp_path):
    # A comment on a pull request needs pull-requests: write, even through the
    # issues API: with issues: write and pull-requests: read, GitHub refused
    # the round marker on pull request #835 with 403 (rework run 43613599819),
    # while pr-review's publish job, holding pull-requests: write, comments on
    # the same pull request. issues: write covers the label swap on the issue.
    used_up = [rest_comment(marker(1, OTHER_HEAD)), rest_comment(marker(2, THIRD_HEAD))]
    paths = _gate_write_paths(tmp_path, []) | _gate_write_paths(tmp_path, used_up)
    pull_request = f"/repos/{REPO}/issues/{PR}/"
    scopes = {"pull-requests" if path.startswith(pull_request) else "issues" for path in paths}
    assert scopes == {"pull-requests", "issues"}, "proceed and handoff write both kinds"
    for scope in scopes:
        assert _job("gate")["permissions"][scope] == "write", scope


def test_job_names_match_the_capacity_check():
    jobs = _workflow()["jobs"]
    assert WORKFLOW.name == rework_gate.REWORK_WORKFLOW
    assert set(jobs) == {rework_gate.GATE_JOB, rework_gate.REWORK_JOB}
    for job in jobs.values():
        assert "name" not in job and "matrix" not in job.get("strategy", {})


def test_every_action_is_sha_pinned():
    for job in _workflow()["jobs"].values():
        for step in job["steps"]:
            if "uses" in step:
                assert SHA_PIN.match(step["uses"]), step["uses"]


def test_the_gate_runs_one_at_a_time_per_pull_request():
    concurrency = _job("gate")["concurrency"]
    assert concurrency["cancel-in-progress"] is False
    assert "github.event.workflow_run.head_branch" in concurrency["group"]
    assert "inputs.pr" in concurrency["group"]
    assert concurrency["group"] != _job("rework")["concurrency"]["group"]


def test_the_model_job_runs_only_after_the_gate_proceeds():
    job = _job("rework")
    assert job["needs"] == "gate"
    assert job["if"] == "needs.gate.outputs.action == 'proceed'"
    assert job["concurrency"]["cancel-in-progress"] is False
    assert job["timeout-minutes"] == 60
    assert _job("gate")["timeout-minutes"] == 10


def test_the_gate_writes_the_marker_before_the_model_job():
    decide = next(step for step in _job("gate")["steps"] if step.get("id") == "decide")
    assert "scripts/rework_gate.py decide" in decide["run"] and "--write" in decide["run"]
    assert "${{" not in decide["run"], "values reach the shell through env only"


def test_findings_reach_the_model_as_a_file_artifact():
    upload = next(
        step for step in _job("gate")["steps"] if "upload-artifact" in step.get("uses", "")
    )
    assert upload["with"]["name"] == "rework-findings"
    assert upload["if"] == "steps.decide.outputs.action == 'proceed'"
    download = next(
        step for step in _job("rework")["steps"] if "download-artifact" in step.get("uses", "")
    )
    assert download["with"] == {"name": "rework-findings", "path": "${{ runner.temp }}/rework"}
    prompt = _model_step()["with"]["prompt"]
    assert '"$RUNNER_TEMP/rework/findings.json"' in prompt
    assert "finding" not in "".join(EXPRESSION.findall(prompt)), "findings never enter the prompt"


def test_action_uses_the_app_token_and_allows_only_the_app_bot():
    inputs = _model_step()["with"]
    assert "github_token" not in inputs
    secret_ref = "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"  # noqa: S105 -- a reference, not a value.
    assert inputs["claude_code_oauth_token"] == secret_ref
    assert inputs["allowed_bots"] == "claude"
    assert "--model ${{ vars.REWORK_MODEL || 'sonnet' }}" in inputs["claude_args"]


def test_prompt_interpolates_only_validated_numbers_and_the_repository():
    prompt = _model_step()["with"]["prompt"]
    assert set(EXPRESSION.findall(prompt)) <= PROMPT_EXPRESSIONS
    validate = _job("rework")["steps"][0]
    assert validate["id"] == "gate" and "^[1-9][0-9]*$" in validate["run"]
    assert "${{" not in validate["run"]


def test_prompt_keeps_the_hard_limits_and_the_stop_rule():
    prompt = _model_step()["with"]["prompt"]
    for limit in (
        "never push to main",
        "never merge",
        "force-push",
        "never enable auto-merge",
        "never delete branches",
        "never touch other branches",
        "never edit files under .github/workflows/",
        "never set labels other than ready-for-human",
        "stage your own edits (`git add -A`) before each run of `scripts/check_all.sh`",
        "that rerun belongs to the same round",
        "A round is red only if its last run is red",
        "after 2 red check rounds, fix the last failure and run `scripts/check_all.sh` once more",
        "only if that run is red too, push nothing",
        "RUN FAILED",
        "$RUNNER_TEMP/run-summary.md",
    ):
        assert limit in prompt, limit


def test_prompt_ends_with_the_summary_also_when_every_finding_is_declined():
    # Issue #843: the summary rule stood before the numbered steps, and the only
    # comment step was tied to a green push, so declining every finding had no ending.
    prompt = _model_step()["with"]["prompt"]
    assert "Every ending writes the summary last" in prompt
    on_green = prompt.index("6. On green:")
    declined = prompt.index("7. If no finding needs a change")
    assert on_green < declined < prompt.index("Hard limits:")
    last_step = prompt[declined : prompt.index("Hard limits:")]
    for rule in (
        "push nothing",
        (
            "post exactly one comment on pull request #${{ steps.gate.outputs.pr }}"
            ' that starts with "> *This was generated by AI.*"'
        ),
        "lists every finding from the file as **declined** with its reason",
        "Then write the summary and end.",
    ):
        assert rule in last_step, rule


def test_checkouts_keep_no_credentials():
    for job in _workflow()["jobs"].values():
        for step in job["steps"]:
            if "actions/checkout@" in step.get("uses", ""):
                assert step["with"]["persist-credentials"] is False


def test_the_report_step_runs_always():
    report = next(step for step in _job("rework")["steps"] if step.get("name") == "Report the run")
    assert report["if"] == "always()"
    assert "scripts/agent_run_report.py" in report["run"]
    assert report["env"] == {"EXECUTION_FILE": "${{ steps.claude.outputs.execution_file }}"}
    assert _model_step()["id"] == "claude"
