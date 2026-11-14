"""Guardrails for the reusable implementer and this repository's caller (ADR-0018).

factory-implementer.yml runs in other repositories too, so caller inputs are
validated before they reach a shell, the prompt or the model's arguments, the
factory's scripts come from the workflow's own commit outside the target's
workspace, and the guards load from there. implementer.yml stays a thin caller.
"""

import json
import os
import re
import subprocess

import implementer_setup
import pytest
from agent_run_workflow_testkit import (
    FACTORY_IMPLEMENTER,
    IMPLEMENTER,
    REPO_ROOT,
    checkouts,
    model_step,
    named_step,
    report_step,
    single_job,
    step_with_id,
    workflow,
)


def test_the_factory_is_fetched_at_the_workflows_own_commit_without_a_token():
    """The scripts match the pinned workflow file, as in factory-pr-review.yml (ADR-0018)."""
    job = single_job(FACTORY_IMPLEMENTER)
    fetch = step_with_id(job, "factory")
    assert fetch["env"] == {
        "SERVER_URL": "${{ github.server_url }}",
        "FACTORY_REPOSITORY": "${{ job.workflow_repository }}",
        "FACTORY_SHA": "${{ job.workflow_sha }}",
    }, "no token reaches the fetch"
    (target,) = checkouts(job)
    assert "repository" not in target["with"], "the only checkout is the caller's repository"
    assert target["with"]["submodules"] == "${{ inputs.submodules }}"


def test_the_factory_fetch_lands_outside_the_workspace_at_the_sha(tmp_path):
    """Run the fetch step against a local repository standing in for GitHub."""
    source = tmp_path / "server" / "owner" / "factory"
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run([*git, "init", "-q", str(source)], check=True)  # noqa: S603
    (source / "marker.txt").write_text("pinned\n", encoding="utf-8")
    subprocess.run([*git, "-C", str(source), "add", "."], check=True)  # noqa: S603
    subprocess.run([*git, "-C", str(source), "commit", "-qm", "pin"], check=True)  # noqa: S603
    sha = subprocess.run(  # noqa: S603
        ["git", "-C", str(source), "rev-parse", "HEAD"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    # GitHub serves a commit by SHA; a local repository has to be told to.
    subprocess.run(  # noqa: S603
        ["git", "-C", str(source), "config", "uploadpack.allowAnySHA1InWant", "true"],  # noqa: S607
        check=True,
    )
    (source / "marker.txt").write_text("later\n", encoding="utf-8")
    subprocess.run([*git, "-C", str(source), "commit", "-qam", "later"], check=True)  # noqa: S603
    runner_temp = tmp_path / "runner"
    runner_temp.mkdir()
    output = tmp_path / "output"
    step = step_with_id(single_job(FACTORY_IMPLEMENTER), "factory")
    result = subprocess.run(  # noqa: S603 -- runs the workflow's own fetch step.
        ["bash", "-e", "-c", step["run"]],  # noqa: S607 -- bash intentionally resolves from PATH.
        env={
            "SERVER_URL": f"file://{tmp_path / 'server'}",
            "FACTORY_REPOSITORY": "owner/factory",
            "FACTORY_SHA": sha,
            "RUNNER_TEMP": str(runner_temp),
            "GITHUB_OUTPUT": str(output),
            "PATH": os.environ["PATH"],
            "HOME": str(tmp_path),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    factory = runner_temp / "factory"
    assert output.read_text(encoding="utf-8") == f"dir={factory}\n"
    assert (factory / "marker.txt").read_text(encoding="utf-8") == "pinned\n"


def test_the_factory_scripts_run_from_the_factory_checkout():
    job = single_job(FACTORY_IMPLEMENTER)
    prompt = model_step(job)["with"]["prompt"]
    assert "python3 scripts/" not in prompt
    assert report_step(job)["env"]["FACTORY_DIR"] == "${{ steps.factory.outputs.dir }}"
    assert '"$FACTORY_DIR/scripts/agent_run_report.py"' in report_step(job)["run"]


def test_factory_declares_its_inputs_and_the_one_secret():
    call = workflow(FACTORY_IMPLEMENTER)[True]["workflow_call"]
    inputs = call["inputs"]
    assert {name: spec.get("default") for name, spec in inputs.items()} == {
        "issue": "",
        "check_command": None,
        "setup_command": "",
        "submodules": False,
        "python_version": "3.12",
        "model": "opus",
        "branch_prefix": implementer_setup.BRANCH_PREFIX,
    }
    assert inputs["check_command"]["required"] is True
    assert call["secrets"] == {"CLAUDE_CODE_OAUTH_TOKEN": {"required": True}}


def test_factory_pins_every_action_to_a_commit():
    for step in single_job(FACTORY_IMPLEMENTER)["steps"]:
        if "uses" in step:
            assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", step["uses"]), step["uses"]


def test_factory_run_steps_take_values_through_env_only():
    for step in single_job(FACTORY_IMPLEMENTER)["steps"]:
        assert "${{" not in step.get("run", ""), f"{step.get('name')}: interpolate through env"


def _run_validation(**values: str) -> subprocess.CompletedProcess:
    step = step_with_id(single_job(FACTORY_IMPLEMENTER), "setup")
    env = {"BRANCH_PREFIX": "agent/issue-", "MODEL": "opus", "CHECK_COMMAND": "make check"}
    assert set(step["env"]) == set(env)
    env.update(values)
    return subprocess.run(  # noqa: S603 -- runs the workflow's own validation step.
        ["bash", "-e", "-c", step["run"]],  # noqa: S607 -- bash intentionally resolves from PATH.
        env={**env, "GITHUB_OUTPUT": os.devnull, "PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"BRANCH_PREFIX": "factory/issue-"},
        {"BRANCH_PREFIX": "agent/"},
        {"MODEL": "claude-opus-4-8[1m]"},
        {"MODEL": "sonnet"},
    ],
)
def test_validation_accepts_good_inputs(values):
    assert _run_validation(**values).returncode == 0


@pytest.mark.parametrize(
    "values",
    [
        {"BRANCH_PREFIX": "agent/issue"},
        {"BRANCH_PREFIX": "a b-"},
        {"BRANCH_PREFIX": "x`id`-"},
        {"BRANCH_PREFIX": ""},
        {"MODEL": "opus --dangerously-skip-permissions"},
        {"MODEL": ""},
        {"CHECK_COMMAND": "  "},
    ],
)
def test_validation_rejects_bad_inputs(values):
    assert _run_validation(**values).returncode != 0


@pytest.mark.parametrize(
    "prefix", ["agent/issue-", "factory/", "a.b_c-", "agent/issue", "a b-", ""]
)
def test_validation_and_the_claim_agree_on_the_branch_prefix(prefix):
    shell_ok = _run_validation(BRANCH_PREFIX=prefix).returncode == 0
    python_ok = implementer_setup.BRANCH_PREFIX_PATTERN.fullmatch(prefix) is not None
    assert shell_ok == python_ok


def test_model_and_prefix_come_from_the_validation_step():
    step = model_step(single_job(FACTORY_IMPLEMENTER))
    assert "--model ${{ steps.setup.outputs.model }}" in step["with"]["claude_args"]
    assert "inputs." not in step["with"]["claude_args"]


def test_setup_command_runs_through_env_and_fails_the_job():
    step = named_step(single_job(FACTORY_IMPLEMENTER), "Run the caller's setup command")
    assert step["env"] == {"SETUP_COMMAND": "${{ inputs.setup_command }}"}
    assert step["if"] == "inputs.setup_command != ''"
    assert step["run"] == 'bash -e -c "$SETUP_COMMAND"'


def test_the_check_command_and_the_guards_are_prepared_from_the_factory(tmp_path):
    """The prompt names the check command's file; the guards load from the factory checkout."""
    job = single_job(FACTORY_IMPLEMENTER)
    step = named_step(job, "Prepare the check command and the guards")
    assert step["env"] == {
        "CHECK_COMMAND": "${{ inputs.check_command }}",
        "FACTORY_DIR": "${{ steps.factory.outputs.dir }}",
        "DEFAULT_BRANCH": "${{ github.event.repository.default_branch }}",
    }
    model = model_step(job)
    assert model["with"]["settings"] == "${{ runner.temp }}/agent-run-settings.json"
    assert 'run the checks with `bash "$RUNNER_TEMP/check-command.sh"`' in model["with"]["prompt"]
    steps = job["steps"]
    assert steps.index(step) < steps.index(model)

    runner_temp = tmp_path / "runner"
    runner_temp.mkdir()
    command = "pytest -q && echo \"$HOME\" '${{ x }}'"
    result = subprocess.run(  # noqa: S603 -- runs the workflow's own preparation step.
        ["bash", "-e", "-c", step["run"]],  # noqa: S607 -- bash intentionally resolves from PATH.
        cwd=tmp_path,
        env={
            "CHECK_COMMAND": command,
            "FACTORY_DIR": str(REPO_ROOT),
            "DEFAULT_BRANCH": "trunk",
            "RUNNER_TEMP": str(runner_temp),
            "PATH": os.environ["PATH"],
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (runner_temp / "check-command.sh").read_text(encoding="utf-8") == command + "\n"
    settings = json.loads((runner_temp / "agent-run-settings.json").read_text(encoding="utf-8"))
    commands = [h["command"] for e in settings["hooks"]["PreToolUse"] for h in e["hooks"]]
    assert f"python3 {REPO_ROOT}/scripts/pr_merge_guard.py --harness claude" in commands
    assert (
        f"python3 {REPO_ROOT}/scripts/default_branch_push_guard.py --harness claude"
        " --default-branch trunk"
    ) in commands


def test_caller_calls_the_local_factory_workflow_with_this_repositorys_inputs():
    assert list(workflow(IMPLEMENTER)["jobs"]) == [implementer_setup.IMPLEMENT_JOB]
    # The Fix task reads the issue from the caller's run-name (ADR-0016).
    assert workflow(IMPLEMENTER)["run-name"] == (
        "implementer: issue #${{ github.event.issue.number || inputs.issue }}"
    )
    job = single_job(IMPLEMENTER)
    assert job["uses"] == "./.github/workflows/factory-implementer.yml"
    assert set(job) == {"permissions", "uses", "with", "secrets"}, (
        "the caller stays thin: no if, concurrency or steps of its own"
    )
    assert job["with"] == {
        "issue": "${{ inputs.issue }}",
        "check_command": "scripts/check_all.sh",
        "setup_command": "pip install -r scripts/check_all.requirements.txt && prek install",
        "submodules": True,
    }


def test_caller_passes_the_secret_by_name_not_inherit():
    secrets = single_job(IMPLEMENTER)["secrets"]
    assert secrets == {"CLAUDE_CODE_OAUTH_TOKEN": "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"}


def test_the_factory_fetch_matches_the_pr_reviews():
    """One mechanism for every factory task (ADR-0018): same env, same git commands."""
    review = workflow(FACTORY_IMPLEMENTER.parent / "factory-pr-review.yml")
    fetches = [
        step
        for job in review["jobs"].values()
        for step in job.get("steps", [])
        if step.get("name") == "Fetch the factory scripts"
    ]
    assert fetches
    implementer = step_with_id(single_job(FACTORY_IMPLEMENTER), "factory")
    assert implementer["name"] == "Fetch the factory scripts"
    for fetch in fetches:
        assert fetch["env"] == implementer["env"]
    expected = [
        line.strip().replace('"$RUNNER_TEMP/factory"', '"$dir"')
        for line in fetches[0]["run"].splitlines()
        if line.strip().startswith("git") or line.strip().startswith('"$SERVER_URL')
    ]
    actual = [
        line.strip()
        for line in implementer["run"].splitlines()
        if line.strip().startswith("git") or line.strip().startswith('"$SERVER_URL')
    ]
    assert actual == expected
