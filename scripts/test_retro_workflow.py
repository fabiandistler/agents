"""Guardrails for the Retro task: factory-retro.yml, its caller retro.yml, the implementer hooks.

The reusable factory-retro.yml holds both jobs (ADR-0017, ADR-0018); this repository's
retro.yml is its thin caller and the gate's eligibility floor.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import retro_counter
import retro_gate
import yaml
from factory_handoff import implementer_run_name

REPO_ROOT = Path(__file__).resolve().parent.parent
CALLER = REPO_ROOT / ".github" / "workflows" / "retro.yml"
RETRO = REPO_ROOT / ".github" / "workflows" / "factory-retro.yml"
IMPLEMENTER = REPO_ROOT / ".github" / "workflows" / "implementer.yml"
# implementer.yml calls it; the called job's artifacts belong to the caller's run.
FACTORY_IMPLEMENTER = REPO_ROOT / ".github" / "workflows" / "factory-implementer.yml"
ACTION = "anthropics/claude-code-action@"
SHA_PIN = re.compile(r"^anthropics/claude-code-action@[0-9a-f]{40}$")
EXPRESSION = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")
PROMPT_EXPRESSIONS = {"steps.pr.outputs.number", "github.repository"}


def _workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _jobs() -> dict:
    return _workflow(RETRO)["jobs"]


def _step(job: dict, predicate) -> dict:
    steps = [step for step in job["steps"] if predicate(step)]
    assert len(steps) == 1
    return steps[0]


def _model_step() -> dict:
    return _step(_jobs()["retro"], lambda step: step.get("uses", "").startswith(ACTION))


def _prompt() -> str:
    return _model_step()["with"]["prompt"]


def test_gate_names_this_workflow_file():
    assert REPO_ROOT / retro_counter.RETRO_WORKFLOW == CALLER


def test_triggers_are_a_daily_schedule_off_the_hour_and_a_manual_run():
    triggers = _workflow(CALLER)[True]
    assert set(triggers) == {"schedule", "workflow_dispatch"}, "no merge trigger (ADR-0017)"
    (entry,) = triggers["schedule"]
    minute, _hour, day, month, weekday = entry["cron"].split()
    assert minute.isdigit() and minute != "0"
    assert (day, month, weekday) == ("*", "*", "*")


def test_the_reusable_workflow_is_called_not_triggered():
    assert set(_workflow(RETRO)[True]) == {"workflow_call"}


def test_gate_and_model_runs_are_serialised_without_cancelling():
    jobs = _jobs()
    assert jobs["gate"]["concurrency"] == {"group": "retro-gate", "cancel-in-progress": False}


def test_caller_calls_the_reusable_workflow_with_the_secret_by_name():
    (job,) = _workflow(CALLER)["jobs"].values()
    assert job["uses"] == f"./.github/workflows/{RETRO.name}"
    assert job["secrets"] == {"CLAUDE_CODE_OAUTH_TOKEN": "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"}
    assert job["with"]["check_command"] == "scripts/check_all.sh"
    assert job["with"]["submodules"] is True
    assert job["with"]["editable_paths"].split() == [
        "scripts/pr_review_prompt.md",
        "scripts/issue_triage_prompt.md",
        "docs/agents/",
        "AGENTS.md",
    ]


def test_caller_caps_the_called_jobs_scopes():
    (job,) = _workflow(CALLER)["jobs"].values()
    assert _workflow(CALLER)["permissions"] == {}
    called = _jobs()
    union = {**called["gate"]["permissions"], **called["retro"]["permissions"]}
    assert job["permissions"] == union


def test_permissions_are_empty_by_default_and_narrow_per_job():
    assert _workflow(RETRO)["permissions"] == {}
    jobs = _jobs()
    assert jobs["gate"]["permissions"] == {
        "contents": "read",
        "pull-requests": "write",
        "issues": "write",
        "actions": "read",
    }
    assert jobs["retro"]["permissions"] == {"contents": "read", "id-token": "write"}


def test_gate_is_model_free_and_labels_before_the_model_job():
    gate = _jobs()["gate"]
    assert not any(ACTION in step.get("uses", "") for step in gate["steps"])
    runs = [step.get("run", "") for step in gate["steps"]]
    select = next(i for i, run in enumerate(runs) if 'retro_gate.py" select' in run)
    context = next(i for i, run in enumerate(runs) if 'retro_gate.py" context' in run)
    assert select < context
    assert _jobs()["retro"]["needs"] == "gate"
    assert _jobs()["retro"]["if"] == "needs.gate.outputs.selected != ''"
    assert "${{ vars.RETRO_EVERY }}" == gate["steps"][select]["env"]["RETRO_EVERY"]


def test_model_job_validates_the_selection_first():
    first = _jobs()["retro"]["steps"][0]
    assert first["id"] == "pr"
    assert "^[1-9][0-9]*$" in first["run"]
    assert "${{" not in first["run"]


def test_action_is_sha_pinned_uses_the_app_token_and_the_model_variable():
    step = _model_step()
    assert SHA_PIN.match(step["uses"])
    assert "github_token" not in step["with"]
    assert "--model ${{ vars.RETRO_MODEL || 'sonnet' }}" in step["with"]["claude_args"]
    assert step["with"]["settings"] == "${{ runner.temp }}/agent-run-settings.json", "guards"


def test_model_default_is_the_skill_audits():
    audit = (REPO_ROOT / ".github" / "workflows" / "skill-audit.yml").read_text(encoding="utf-8")
    match = re.search(r"--model (\w+)", audit)
    assert match, "skill-audit.yml names no model"
    alias = match.group(1)
    assert f"vars.RETRO_MODEL || '{alias}'" in _model_step()["with"]["claude_args"]


def test_prompt_interpolates_no_event_text():
    used = set(EXPRESSION.findall(_prompt()))
    assert used <= PROMPT_EXPRESSIONS, f"unexpected expressions in the prompt: {used}"


def test_prompt_names_the_validated_path_file_and_the_vendored_exclusion():
    prompt = _prompt()
    assert '"$RUNNER_TEMP/editable-paths.txt"' in prompt
    assert "linguist-vendored" in prompt
    assert "factory/docs/agents/retro.md" in prompt
    assert "No issue: <reason>. Refs #" in prompt


def _validation_step() -> dict:
    return _step(_jobs()["retro"], lambda step: step.get("name") == "Validate the caller's inputs")


def _validate(tmp_path, paths: str, command: str = "scripts/check_all.sh"):
    env = {
        **os.environ,
        "CHECK_COMMAND": command,
        "EDITABLE_PATHS": paths,
        "RUNNER_TEMP": str(tmp_path),
    }
    return subprocess.run(  # noqa: S603
        [shutil.which("bash") or "bash", "-c", _validation_step()["run"]],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )


def test_validation_step_takes_inputs_through_env_only():
    step = _validation_step()
    assert "${{" not in step["run"]
    assert set(step["env"]) == {"CHECK_COMMAND", "EDITABLE_PATHS"}


def test_editable_paths_are_written_one_per_line(tmp_path):
    done = _validate(tmp_path, "AGENTS.md\n\ndocs/agents/\ninstructions/review-standards.md\n")
    assert done.returncode == 0, done.stderr
    assert (tmp_path / "editable-paths.txt").read_text().splitlines() == [
        "AGENTS.md",
        "docs/agents/",
        "instructions/review-standards.md",
    ]
    assert (tmp_path / "check-command.sh").read_text() == "scripts/check_all.sh\n"


@pytest.mark.parametrize(
    "paths",
    [
        "",
        "   \n",
        "../etc/passwd",
        "docs/../.github/workflows/x.yml",
        "/etc/passwd",
        ".github/workflows/ci.yml",
        ".claude/settings.json",
        ".git/config",
        "docs/$(id)",
        "docs/a b.md",
    ],
)
def test_an_unusable_editable_path_fails_the_job(tmp_path, paths):
    done = _validate(tmp_path, paths)
    assert done.returncode != 0
    assert "::error::editable_paths" in done.stdout


def test_an_empty_check_command_fails_the_job(tmp_path):
    done = _validate(tmp_path, "AGENTS.md", command="  ")
    assert done.returncode != 0
    assert "::error::check_command" in done.stdout


def test_prompt_keeps_the_hard_limits():
    prompt = _prompt()
    for limit in (
        "never push to main",
        "never merge",
        "never force-push",
        "never enable auto-merge",
        "never delete branches",
        "never edit files under .github/workflows/",
        "never write to issues or PRs other than your own Retro PR",
        "RUN FAILED",
        "$RUNNER_TEMP/run-summary.md",
    ):
        assert limit in prompt, f"prompt lost {limit!r}"


def test_prompt_ends_every_run_with_the_summary():
    # Issue #843: the runbook's last step opens the pull request and names no summary.
    prompt = _prompt()
    assert "Every ending writes the summary last, also where the runbook does not name it." in (
        prompt
    )


def test_report_step_runs_always():
    report = _step(_jobs()["retro"], lambda step: step.get("name") == "Report the run")
    assert report["if"] == "always()"
    assert "agent_run_report.py" in report["run"]


def test_checkouts_keep_no_credentials():
    for job in _jobs().values():
        for step in job["steps"]:
            if "actions/checkout@" in step.get("uses", ""):
                assert step["with"]["persist-credentials"] is False


def test_implementer_run_name_is_the_title_the_gate_looks_for():
    run_name = _workflow(IMPLEMENTER)["run-name"]
    assert run_name == implementer_run_name("${{ github.event.issue.number || inputs.issue }}")
    assert retro_gate.IMPLEMENTER_WORKFLOW == IMPLEMENTER.name


def test_implementer_keeps_its_run_summary_after_the_report():
    (caller,) = _workflow(IMPLEMENTER)["jobs"].values()
    assert caller["uses"] == f"./.github/workflows/{FACTORY_IMPLEMENTER.name}"
    steps = next(iter(_workflow(FACTORY_IMPLEMENTER)["jobs"].values()))["steps"]
    names = [step.get("name") for step in steps]
    upload = steps[names.index("Keep the run summary")]
    assert names.index("Report the run") < names.index("Keep the run summary")
    assert upload["if"] == "always()"
    assert upload["uses"].startswith("actions/upload-artifact@")
    assert upload["with"]["name"] == retro_gate.SUMMARY_ARTIFACT
    assert upload["with"]["path"] == "${{ runner.temp }}/run-summary.md"
