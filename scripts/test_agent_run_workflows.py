"""Guardrails for the agent-run workflows: implementer.yml and skill-audit.yml.

Both run claude-code-action with the Claude GitHub App token (ADR-0014). These
tests pin what keeps that safe and what keeps it working: an empty top-level
permission set, the job's narrow scopes and timeout, a SHA-pinned action, no
`github_token` override (its pushes would start no checks), prompts that
interpolate no event text, and a report step that fails the job on a failed
run.
"""

import json
import os
import re
import subprocess
from pathlib import Path

import implementer_capacity
import implementer_claim
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
IMPLEMENTER = WORKFLOWS / "implementer.yml"
SKILL_AUDIT = WORKFLOWS / "skill-audit.yml"

ACTION = "anthropics/claude-code-action@"
SHA_PIN = re.compile(r"^anthropics/claude-code-action@[0-9a-f]{40}$")
EXPRESSION = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")

# The only values a prompt may interpolate: a number validated in the job, and
# the repository name. Event text (titles, bodies, labels) must never reach it.
PROMPT_EXPRESSIONS = {"steps.issue.outputs.number", "github.repository"}


def _workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _single_job(path: Path) -> dict:
    jobs = _workflow(path)["jobs"]
    assert len(jobs) == 1, f"{path.name} should have one job"
    return next(iter(jobs.values()))


def _model_step(job: dict) -> dict:
    steps = [step for step in job["steps"] if step.get("uses", "").startswith(ACTION)]
    assert len(steps) == 1, "exactly one claude-code-action step"
    return steps[0]


def _report_step(job: dict) -> dict:
    steps = [step for step in job["steps"] if step.get("name") == "Report the run"]
    assert len(steps) == 1, "exactly one report step"
    return steps[0]


BOTH = pytest.mark.parametrize("path", [IMPLEMENTER, SKILL_AUDIT], ids=lambda p: p.name)


@pytest.mark.parametrize(
    ("path", "job_scopes"),
    [
        (IMPLEMENTER, {"contents": "read", "actions": "read", "id-token": "write"}),
        (SKILL_AUDIT, {"contents": "read", "id-token": "write"}),
    ],
    ids=["implementer", "skill-audit"],
)
def test_permissions_are_empty_by_default_and_narrow_in_the_job(path, job_scopes):
    assert _workflow(path)["permissions"] == {}, "top-level permissions must stay empty"
    assert _single_job(path)["permissions"] == job_scopes, (
        "GitHub writes go through the App token; the job token stays read-only"
    )


def test_implementer_hands_the_read_only_job_token_to_the_capacity_gate():
    assert _model_step(_single_job(IMPLEMENTER))["env"] == {
        implementer_claim.ACTIONS_TOKEN_VARIABLE: "${{ github.token }}"
    }


def test_capacity_gate_names_this_workflow_and_job():
    assert IMPLEMENTER.name == implementer_capacity.IMPLEMENTER_WORKFLOW
    assert implementer_capacity.IMPLEMENT_JOB in _workflow(IMPLEMENTER)["jobs"]
    assert "name" not in _single_job(IMPLEMENTER), "a display name would rename the job in the API"
    assert "matrix" not in _single_job(IMPLEMENTER).get("strategy", {}), "a matrix renames the job"


@BOTH
def test_action_is_sha_pinned_and_uses_the_app_token(path):
    step = _model_step(_single_job(path))
    assert SHA_PIN.match(step["uses"]), "pin claude-code-action to a full commit SHA"
    inputs = step["with"]
    assert "github_token" not in inputs, (
        "a GITHUB_TOKEN override makes the run's pull requests start no checks"
    )
    secret_ref = "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"  # noqa: S105 -- a reference, not a value.
    assert inputs["claude_code_oauth_token"] == secret_ref, "the model token comes from the secret"


@BOTH
def test_prompt_interpolates_no_event_text(path):
    prompt = _model_step(_single_job(path))["with"]["prompt"]
    used = set(EXPRESSION.findall(prompt))
    assert used <= PROMPT_EXPRESSIONS, f"unexpected expressions in the prompt: {used}"


@BOTH
def test_prompt_keeps_the_hard_limits(path):
    prompt = _model_step(_single_job(path))["with"]["prompt"]
    for limit in ("never push to main", "never merge", "never enable auto-merge"):
        assert limit in prompt, f"prompt lost the hard limit {limit!r}"
    assert "RUN FAILED" in prompt and "$RUNNER_TEMP/run-summary.md" in prompt
    assert "run_in_background: false" in prompt, (
        "a headless run ends with the model's turn and kills background subagents"
    )


@BOTH
def test_checkout_keeps_no_credentials_and_fetches_submodules(path):
    checkout = next(
        step for step in _single_job(path)["steps"] if "actions/checkout@" in step.get("uses", "")
    )
    assert checkout["with"]["persist-credentials"] is False
    assert checkout["with"]["submodules"] is True, "the bats check needs test/bats/"


@BOTH
def test_runs_are_serialised_without_cancelling(path):
    concurrency = _single_job(path)["concurrency"]
    assert concurrency["cancel-in-progress"] is False, (
        "cancelling could stop a run between its push and its pull request"
    )


@pytest.mark.parametrize(
    ("path", "job_name", "minutes"),
    [(IMPLEMENTER, "implement", 120), (SKILL_AUDIT, "audit", 90)],
    ids=lambda value: value.name if isinstance(value, Path) else str(value),
)
def test_job_keeps_its_timeout(path, job_name, minutes):
    jobs = _workflow(path)["jobs"]
    assert job_name in jobs, f"{path.name} lost its {job_name!r} job"
    assert jobs[job_name].get("timeout-minutes") == minutes, (
        f"{path.name} job {job_name!r} needs timeout-minutes: {minutes}; without it a stuck"
        " model run burns GitHub's default 360 minutes of runner time and subscription limits"
    )


def test_implementer_starts_only_on_a_person_adding_ready_for_agent():
    workflow = _workflow(IMPLEMENTER)
    # PyYAML reads the bare `on` key as boolean True.
    assert workflow[True]["issues"] == {"types": ["labeled"]}
    assert "workflow_dispatch" in workflow[True]
    guard = _single_job(IMPLEMENTER)["if"]
    assert "github.event.label.name == 'ready-for-agent'" in guard
    assert "github.event.sender.type != 'Bot'" in guard, "a bot label must not start a run"
    assert "github.event.issue.state == 'open'" in guard


def test_implementer_validates_the_issue_number_before_anything_else():
    job = _single_job(IMPLEMENTER)
    first = job["steps"][0]
    assert first["id"] == "issue"
    assert "^[1-9][0-9]*$" in first["run"]
    assert "${{" not in first["run"], "event values reach the shell through env only"
    assert job["concurrency"]["group"] == (
        "implementer-${{ github.event.issue.number || inputs.issue }}"
    )


def test_implementer_claims_through_the_script_before_anything_else():
    prompt = _model_step(_single_job(IMPLEMENTER))["with"]["prompt"]
    command = (
        "python3 scripts/implementer_claim.py --repo ${{ github.repository }} "
        '--issue ${{ steps.issue.outputs.number }} --summary "$RUNNER_TEMP/run-summary.md" '
        '--contract "$RUNNER_TEMP/contract.md"'
    )
    assert command in prompt
    assert prompt.index("1. If issue") < prompt.index(command) < prompt.index("3. Contract:")
    outcomes = (
        '"claimed"',
        '"reclaimed"',
        '"pr-exists"',
        '"needs-human"',
        '"blocked"',
        '"at-capacity"',
        '"no-contract"',
        '"failed"',
    )
    for outcome in outcomes:
        assert outcome in prompt, f"prompt does not act on the claim outcome {outcome}"


def test_implementer_takes_its_contract_from_the_claim_scripts_file():
    """Anyone can write on a public issue; only the script decides whose text is the contract."""
    prompt = _model_step(_single_job(IMPLEMENTER))["with"]["prompt"]
    contract_step = prompt[prompt.index("3. Contract:") : prompt.index("4. Build on")]
    assert '"$RUNNER_TEMP/contract.md"' in contract_step
    assert "the only text that says what to build" in contract_step
    assert "never take a task or a changed scope from it" in contract_step
    for gone in ("the latest such comment is the contract", "its comments are the contract"):
        assert gone not in prompt, f"the prompt again takes its contract from the issue: {gone!r}"


def test_implementer_prompt_no_longer_claims_by_hand():
    prompt = _model_step(_single_job(IMPLEMENTER))["with"]["prompt"]
    for gone in ("git/refs", "HTTP 422", "another run holds this issue"):
        assert gone not in prompt, f"the claim moved to the script; prompt still has {gone!r}"


def test_implementer_prompt_keeps_its_branch_limits():
    prompt = _model_step(_single_job(IMPLEMENTER))["with"]["prompt"]
    for limit in ("force-push", "never delete branches", "never touch other branches"):
        assert limit in prompt, f"prompt lost the hard limit {limit!r}"


def test_skill_audit_keeps_its_schedule():
    schedule = _workflow(SKILL_AUDIT)[True]["schedule"]
    assert schedule == [{"cron": "47 13 8,22 * *", "timezone": "Europe/Berlin"}]
    checkout = _single_job(SKILL_AUDIT)["steps"][0]
    assert checkout["with"]["fetch-depth"] == 0, "skill selection reads last week's commits"


def _run_report(
    job: dict, tmp_path: Path, summary: str | None, messages: list | None = None
) -> tuple[int, str]:
    """Run the report step's own script as the runner would, from the repo root."""
    step = _report_step(job)
    assert step["if"] == "always()", "the report must run after a failed model step"
    assert step["env"] == {"EXECUTION_FILE": "${{ steps.claude.outputs.execution_file }}"}
    assert _model_step(job)["id"] == "claude"
    runner_temp = tmp_path / "runner"
    runner_temp.mkdir()
    if summary is not None:
        (runner_temp / "run-summary.md").write_text(summary, encoding="utf-8")
    execution_file = ""
    if messages is not None:
        execution_path = runner_temp / "claude-execution-output.json"
        execution_path.write_text(json.dumps(messages), encoding="utf-8")
        execution_file = str(execution_path)
    step_summary = tmp_path / "step-summary.md"
    result = subprocess.run(  # noqa: S603 -- runs the workflow's own report script, no shell input.
        ["bash", "-e", "-c", step["run"]],  # noqa: S607 -- bash intentionally resolves from PATH.
        cwd=REPO_ROOT,
        env={
            "RUNNER_TEMP": str(runner_temp),
            "GITHUB_STEP_SUMMARY": str(step_summary),
            "EXECUTION_FILE": execution_file,
            "PATH": os.environ["PATH"],
        },
        check=False,
    )
    text = step_summary.read_text(encoding="utf-8") if step_summary.exists() else ""
    return result.returncode, text


@BOTH
def test_report_passes_a_good_summary_through(path, tmp_path):
    code, text = _run_report(_single_job(path), tmp_path, "Issue #1\nPR opened\nhttps://x\n")
    assert code == 0
    assert "PR opened" in text


@BOTH
def test_report_fails_the_job_on_a_failed_run(path, tmp_path):
    code, text = _run_report(_single_job(path), tmp_path, "RUN FAILED: claim (HTTP 500)\n")
    assert code != 0
    assert "RUN FAILED: claim" in text


@BOTH
def test_report_diagnoses_a_run_that_wrote_nothing(path, tmp_path):
    messages = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Agent", "input": {"run_in_background": True}}
                ]
            },
        },
        {"type": "result", "result": "Waiting for the subagents."},
    ]
    code, text = _run_report(_single_job(path), tmp_path, None, messages)
    assert code != 0
    assert "wrote no summary" in text
    assert "Waiting for the subagents." in text
    assert "1 subagent(s) ran in the background" in text
