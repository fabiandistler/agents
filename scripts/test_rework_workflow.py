"""Guardrails for the Rework task (ADR-0015, ADR-0018).

The reusable factory-rework.yml holds both jobs; this repository's rework.yml
is its thin caller. The model-free gate writes with GITHUB_TOKEN; the model job
runs claude-code-action with the Claude GitHub App token. These tests pin what
keeps that safe: empty top-level permissions, narrow job scopes, a SHA-pinned
action, no `github_token` override, no event text in the prompt, findings
handed over as a file artifact, validated caller inputs, the factory scripts
fetched at the workflow's own commit, and the report step.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import cast

import factory_handoff
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
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
CALLER = WORKFLOWS / "rework.yml"
WORKFLOW = WORKFLOWS / "factory-rework.yml"

ACTION = "anthropics/claude-code-action@"
SHA_PIN = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")
EXPRESSION = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")
PROMPT_EXPRESSIONS = {
    "steps.gate.outputs.pr",
    "steps.gate.outputs.issue",
    "steps.gate.outputs.round",
    "github.repository",
}


def _workflow(path: Path = WORKFLOW) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _job(name: str) -> dict:
    return _workflow()["jobs"][name]


def _model_step() -> dict:
    steps = [step for step in _job("rework")["steps"] if step.get("uses", "").startswith(ACTION)]
    assert len(steps) == 1, "exactly one claude-code-action step"
    return steps[0]


def test_triggers_on_a_completed_review_or_a_manual_run_never_a_label():
    triggers = _workflow(CALLER)[True]
    assert triggers["workflow_run"] == {"workflows": ["pr-review"], "types": ["completed"]}
    assert triggers["workflow_dispatch"]["inputs"]["pr"]["required"] is True
    assert set(triggers) == {"workflow_run", "workflow_dispatch"}


def test_the_head_branch_filter_uses_the_default_agent_branch_prefix():
    condition = _job("gate")["if"]
    filters = re.findall(
        r"startsWith\(github\.event\.workflow_run\.head_branch, '([^']*)'\)", condition
    )
    assert filters == [factory_handoff.AGENT_BRANCH_PREFIX]


def test_permissions_are_empty_by_default_and_narrow_in_each_job():
    assert _workflow()["permissions"] == {}
    assert _workflow(CALLER)["permissions"] == {}
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
    # The capacity check lists the caller's runs and matches the called jobs
    # by their composed names, `<caller job> / gate` (agent_run_capacity.is_job).
    jobs = _workflow()["jobs"]
    assert CALLER.name == rework_gate.REWORK_WORKFLOW
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
    assert '"$FACTORY_DIR/scripts/rework_gate.py" decide' in decide["run"]
    assert "--write" in decide["run"]
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
    assert "--model ${{ steps.setup.outputs.model }}" in inputs["claude_args"]
    assert "inputs." not in inputs["claude_args"]


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
        'run the checks with `bash "$RUNNER_TEMP/check-command.sh"`',
        "stage your own edits (`git add -A`) before each run of the checks",
        "that rerun belongs to the same round",
        "A round is red only if its last run is red",
        "after 2 red check rounds, fix the last failure and run the checks once more",
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
    on_green_at = prompt.index("6. On green:")
    declined_at = prompt.index("7. If no finding needs a change")
    hard_limits_at = prompt.index("Hard limits:")
    assert on_green_at < declined_at < hard_limits_at
    last_step = prompt[declined_at:hard_limits_at]
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
    assert '"$FACTORY_DIR/scripts/agent_run_report.py"' in report["run"]
    assert report["env"] == {
        "EXECUTION_FILE": "${{ steps.claude.outputs.execution_file }}",
        "FACTORY_DIR": "${{ steps.factory.outputs.dir }}",
    }
    assert _model_step()["id"] == "claude"


def _fetch_lines(run: str) -> list[str]:
    return [
        line.strip().replace('"$RUNNER_TEMP/factory"', '"$dir"')
        for line in run.splitlines()
        if line.strip().startswith(("git", '"$SERVER_URL'))
    ]


def test_both_jobs_fetch_the_factory_as_the_pr_review_does():
    """One mechanism for every factory task (ADR-0018): same env, same git commands."""
    review = _workflow(WORKFLOWS / "factory-pr-review.yml")
    (reference, *_) = [
        step
        for job in review["jobs"].values()
        for step in job.get("steps", [])
        if step.get("name") == "Fetch the factory scripts"
    ]
    for name in (rework_gate.GATE_JOB, rework_gate.REWORK_JOB):
        (fetch,) = [step for step in _job(name)["steps"] if step.get("id") == "factory"]
        assert fetch["name"] == "Fetch the factory scripts"
        assert fetch["env"] == reference["env"], "no token reaches the fetch"
        assert _fetch_lines(fetch["run"]) == _fetch_lines(reference["run"])


def test_the_factory_scripts_run_from_the_factory_checkout():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python3 scripts/" not in text
    assert [s for s in _job("gate")["steps"] if "actions/checkout@" in s.get("uses", "")] == []
    for step in _job("gate")["steps"]:
        if "rework_gate.py" in step.get("run", ""):
            assert step["env"]["FACTORY_DIR"] == "${{ steps.factory.outputs.dir }}"


def test_run_steps_take_values_through_env_only():
    for job in _workflow()["jobs"].values():
        for step in job["steps"]:
            assert "${{" not in step.get("run", ""), f"{step.get('name')}: interpolate through env"


def test_factory_declares_its_inputs_and_the_one_secret():
    call = _workflow()[True]["workflow_call"]
    assert set(_workflow()[True]) == {"workflow_call"}
    inputs = call["inputs"]
    assert {name: spec.get("default") for name, spec in inputs.items()} == {
        "pr": "",
        "check_command": None,
        "setup_command": "",
        "submodules": False,
        "python_version": "3.12",
        "model": "sonnet",
    }
    assert inputs["check_command"]["required"] is True
    assert call["secrets"] == {"CLAUDE_CODE_OAUTH_TOKEN": {"required": True}}


def test_the_target_checkout_takes_the_callers_submodules():
    (checkout,) = [s for s in _job("rework")["steps"] if "actions/checkout@" in s.get("uses", "")]
    assert checkout["with"]["submodules"] == "${{ inputs.submodules }}"
    assert checkout["with"]["ref"] == "agent/issue-${{ steps.gate.outputs.issue }}"
    assert "repository" not in checkout["with"]


def test_the_check_command_and_the_guards_are_prepared_before_the_model_step():
    steps = _job("rework")["steps"]
    prepare = next(s for s in steps if s.get("name") == "Prepare the check command and the guards")
    implementer = yaml.safe_load(
        (WORKFLOWS / "factory-implementer.yml").read_text(encoding="utf-8")
    )["jobs"]["implement"]["steps"]
    same = next(s for s in implementer if s.get("name") == prepare["name"])
    assert prepare["env"] == same["env"] and prepare["run"] == same["run"]
    setup = next(s for s in steps if s.get("name") == "Run the caller's setup command")
    assert setup["env"] == {"SETUP_COMMAND": "${{ inputs.setup_command }}"}
    assert setup["run"] == 'bash -e -c "$SETUP_COMMAND"'
    model = _model_step()
    assert model["with"]["settings"] == "${{ runner.temp }}/agent-run-settings.json"
    assert steps.index(prepare) < steps.index(model)


def _run_validation(**values: str) -> subprocess.CompletedProcess:
    step = next(s for s in _job("rework")["steps"] if s.get("id") == "setup")
    env = {"MODEL": "sonnet", "CHECK_COMMAND": "make check"}
    assert set(step["env"]) == set(env)
    env.update(values)
    return subprocess.run(  # noqa: S603 -- runs the workflow's own validation step.
        ["bash", "-e", "-c", step["run"]],  # noqa: S607 -- bash intentionally resolves from PATH.
        env={**env, "GITHUB_OUTPUT": os.devnull, "PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
    )


def test_validation_accepts_good_inputs():
    for values in ({}, {"MODEL": "claude-opus-4-8[1m]"}, {"MODEL": "opus"}):
        assert _run_validation(**values).returncode == 0, values


def test_validation_rejects_bad_inputs():
    for values in (
        {"MODEL": "sonnet --dangerously-skip-permissions"},
        {"MODEL": ""},
        {"CHECK_COMMAND": "  "},
    ):
        assert _run_validation(**values).returncode != 0, values


def test_caller_calls_the_local_factory_workflow_with_this_repositorys_inputs():
    jobs = _workflow(CALLER)["jobs"]
    assert list(jobs) == ["rework"]
    job = jobs["rework"]
    assert job["uses"] == "./.github/workflows/factory-rework.yml"
    assert set(job) == {"permissions", "uses", "with", "secrets"}, (
        "the caller stays thin: no if, concurrency or steps of its own"
    )
    assert job["with"] == {
        "pr": "${{ inputs.pr }}",
        "check_command": "scripts/check_all.sh",
        "setup_command": "pip install -r scripts/check_all.requirements.txt && prek install",
        "submodules": True,
        "model": "${{ vars.REWORK_MODEL || 'sonnet' }}",
    }
    secret_ref = "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"  # noqa: S105 -- a reference, not a value.
    assert job["secrets"] == {"CLAUDE_CODE_OAUTH_TOKEN": secret_ref}


def test_caller_permissions_are_the_union_of_the_called_jobs():
    union: dict[str, str] = {}
    for job in _workflow()["jobs"].values():
        for scope, level in job["permissions"].items():
            union[scope] = "write" if "write" in (level, union.get(scope)) else level
    assert _workflow(CALLER)["jobs"]["rework"]["permissions"] == union
