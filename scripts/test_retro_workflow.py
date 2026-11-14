"""Guardrails for .github/workflows/retro.yml and the implementer's Retro hooks (ADR-0017)."""

import re
from pathlib import Path

import retro_gate
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
RETRO = REPO_ROOT / ".github" / "workflows" / "retro.yml"
IMPLEMENTER = REPO_ROOT / ".github" / "workflows" / "implementer.yml"
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
    assert REPO_ROOT / retro_gate.RETRO_WORKFLOW == RETRO


def test_triggers_are_a_daily_schedule_off_the_hour_and_a_manual_run():
    triggers = _workflow(RETRO)[True]
    assert set(triggers) == {"schedule", "workflow_dispatch"}, "no merge trigger (ADR-0017)"
    (entry,) = triggers["schedule"]
    minute, _hour, day, month, weekday = entry["cron"].split()
    assert minute.isdigit() and minute != "0"
    assert (day, month, weekday) == ("*", "*", "*")


def test_runs_are_serialised_without_cancelling():
    assert _workflow(RETRO)["concurrency"] == {"group": "retro", "cancel-in-progress": False}


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
    select = next(i for i, run in enumerate(runs) if "retro_gate.py select" in run)
    context = next(i for i, run in enumerate(runs) if "retro_gate.py context" in run)
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


def test_model_default_is_the_skill_audits():
    audit = (REPO_ROOT / ".github" / "workflows" / "skill-audit.yml").read_text(encoding="utf-8")
    match = re.search(r"--model (\w+)", audit)
    assert match, "skill-audit.yml names no model"
    alias = match.group(1)
    assert f"vars.RETRO_MODEL || '{alias}'" in _model_step()["with"]["claude_args"]


def test_prompt_interpolates_no_event_text():
    used = set(EXPRESSION.findall(_prompt()))
    assert used <= PROMPT_EXPRESSIONS, f"unexpected expressions in the prompt: {used}"


def test_prompt_states_the_path_allowlist_and_the_vendored_exclusion():
    prompt = _prompt()
    for path in (
        "scripts/pr_review_prompt.md",
        "scripts/issue_triage_prompt.md",
        "docs/agents/",
        "AGENTS.md",
    ):
        assert path in prompt
    assert "linguist-vendored" in prompt
    assert ".claude/skills/triage/AGENT-BRIEF.md" in prompt
    assert "docs/agents/retro.md" in prompt
    assert "No issue: <reason>. Refs #" in prompt


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
        "run_in_background: false",
        "RUN FAILED",
        "$RUNNER_TEMP/run-summary.md",
    ):
        assert limit in prompt, f"prompt lost {limit!r}"


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
    assert run_name == "implementer: issue #${{ github.event.issue.number || inputs.issue }}"
    assert retro_gate.IMPLEMENTER_WORKFLOW == IMPLEMENTER.name


def test_implementer_keeps_its_run_summary_after_the_report():
    steps = next(iter(_workflow(IMPLEMENTER)["jobs"].values()))["steps"]
    names = [step.get("name") for step in steps]
    upload = steps[names.index("Keep the run summary")]
    assert names.index("Report the run") < names.index("Keep the run summary")
    assert upload["if"] == "always()"
    assert upload["uses"].startswith("actions/upload-artifact@")
    assert upload["with"]["name"] == retro_gate.SUMMARY_ARTIFACT
    assert upload["with"]["path"] == "${{ runner.temp }}/run-summary.md"
