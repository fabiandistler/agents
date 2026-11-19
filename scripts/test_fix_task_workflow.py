"""Guardrails for the model-free Fix task (ADR-0016, ADR-0018).

The reusable factory-fix-task.yml holds the job; this repository's fix-task.yml
is its thin caller with the watch list.
"""

import re
from pathlib import Path

import factory_failure_policy
import yaml
from factory_handoff import implementer_run_name

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
WORKFLOW = WORKFLOWS / "fix-task.yml"
FACTORY = WORKFLOWS / "factory-fix-task.yml"
SCOPES = {"issues": "write", "actions": "read", "checks": "read"}


def _workflow(path: Path = WORKFLOW) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _job(path: Path = WORKFLOW) -> dict:
    jobs = _workflow(path)["jobs"]
    assert len(jobs) == 1, "the Fix task is one job"
    return next(iter(jobs.values()))


def test_permissions_are_empty_by_default_and_three_scopes_in_the_job():
    for path in (WORKFLOW, FACTORY):
        assert _workflow(path)["permissions"] == {}
        assert _job(path)["permissions"] == SCOPES


def test_concurrency_is_per_watched_workflow_and_never_cancels():
    concurrency = _job(FACTORY)["concurrency"]
    assert "github.event.workflow_run.name" in concurrency["group"]
    assert concurrency["cancel-in-progress"] is False


def test_it_watches_exactly_the_policy_workflows_and_not_itself():
    on = _workflow()[True]  # YAML 1.1 reads the `on` key as True
    watched = on["workflow_run"]["workflows"]
    names = {
        yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))["name"]
        for path in factory_failure_policy.WATCHED_WORKFLOWS
    }
    assert set(watched) == names
    assert _workflow()["name"] not in watched and "CI" not in watched
    assert on["workflow_run"]["types"] == ["completed"]
    assert on["workflow_dispatch"]["inputs"]["dry_run"]["default"] is True


def test_it_watches_the_rework_and_retro_tasks():
    watched = _workflow()[True]["workflow_run"]["workflows"]
    assert {"rework", "retro"} <= set(watched)


def test_every_watched_workflow_starts_runs_of_its_own():
    # A called (workflow_call) workflow runs inside its caller's run: its
    # failure is the caller's failed run, under the caller's name and path. So
    # the callers are watched, never the called files.
    for path in factory_failure_policy.WATCHED_WORKFLOWS:
        triggers = yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))[True]
        assert set(triggers) - {"workflow_call"}, path


def test_no_model_and_no_app_token():
    text = WORKFLOW.read_text(encoding="utf-8") + FACTORY.read_text(encoding="utf-8")
    for forbidden in ("claude", "anthropic", "CLAUDE_CODE_OAUTH_TOKEN", "id-token", "app-token"):
        assert forbidden.lower() not in text.lower().replace("claude-code", "")
    secrets = set(re.findall(r"secrets\.([A-Z_]+)", text))
    assert secrets == {"GITHUB_TOKEN"}
    assert "secrets" not in _job(), "the caller passes no secret"


def test_the_implementer_run_name_matches_the_policy():
    run_name = yaml.safe_load(
        (REPO_ROOT / ".github/workflows/implementer.yml").read_text(encoding="utf-8")
    )["run-name"]
    assert run_name == implementer_run_name("${{ github.event.issue.number || inputs.issue }}")
    assert (
        factory_failure_policy.fix_issue_number(
            {"path": factory_failure_policy.IMPLEMENTER, "display_title": implementer_run_name(783)}
        )
        == 783
    )


def test_caller_calls_the_local_factory_workflow_and_stays_thin():
    job = _job()
    assert job["uses"] == "./.github/workflows/factory-fix-task.yml"
    assert set(job) == {"permissions", "uses", "with"}, "no if, concurrency or steps of its own"
    assert job["with"] == {
        "run_id": "${{ inputs.run_id }}",
        "dry_run": "${{ inputs.dry_run != false }}",
    }
    assert "concurrency" not in _workflow()


def test_factory_declares_its_inputs_and_no_secret():
    triggers = _workflow(FACTORY)[True]
    assert set(triggers) == {"workflow_call"}
    call = triggers["workflow_call"]
    assert {name: spec.get("default") for name, spec in call["inputs"].items()} == {
        "run_id": "",
        "dry_run": True,
    }
    assert "secrets" not in call


def test_factory_writes_only_for_an_event_or_an_explicit_manual_write():
    step = next(s for s in _job(FACTORY)["steps"] if s.get("name") == "File the failure")
    assert step["env"]["WRITE"] == (
        "${{ github.event_name != 'workflow_dispatch' || !inputs.dry_run }}"
    )
    assert step["env"]["RUN_ID"] == "${{ github.event.workflow_run.id || inputs.run_id }}"
    assert '"$FACTORY_DIR/scripts/factory_failure.py"' in step["run"]
    assert "${{" not in step["run"]


def test_factory_runs_the_script_from_the_fetched_factory_without_a_checkout():
    steps = _job(FACTORY)["steps"]
    assert not [s for s in steps if "actions/checkout@" in s.get("uses", "")]
    fetch = next(s for s in steps if s.get("id") == "factory")
    review = _workflow(WORKFLOWS / "factory-pr-review.yml")
    reference = next(
        step
        for job in review["jobs"].values()
        for step in job.get("steps", [])
        if step.get("name") == "Fetch the factory scripts"
    )
    assert fetch["name"] == reference["name"]
    assert fetch["env"] == reference["env"], "no token reaches the fetch"

    def lines(run: str) -> list[str]:
        return [
            line.strip().replace('"$RUNNER_TEMP/factory"', '"$dir"')
            for line in run.splitlines()
            if line.strip().startswith(("git", '"$SERVER_URL'))
        ]

    assert lines(fetch["run"]) == lines(reference["run"])
    for step in steps:
        if "uses" in step:
            assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", step["uses"]), step["uses"]
