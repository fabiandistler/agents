"""The reusable PR review hands each caller input to the script that acts on it.

The steps of .github/workflows/factory-pr-review.yml run here under bash: the
factory checkout is a symlink to this scripts/ directory, and where a test
must see the command line, `python3` is a stub that records its argv. So
`standards_path` is shown to reach `pr_review.py --standards`, `quiet_logs` to
keep the plan out of the log, and `fail_on_unavailable` and the skip prefixes
to reach the publisher (their effect is tested in
test_pr_publish_caller_options.py and test_pr_skip.py).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pr_workflow_testkit import (
    MODEL_KEY,
    REPO_ROOT,
    job_env,
    job_named,
    load_workflow_text,
    normalize,
    parse_workflow,
    step_running,
    steps_of,
)

# What the publisher stub prints: stands in for the plan JSON and its model text.
PLAN_MARKER = "PLAN-JSON-WITH-MODEL-TEXT"
EXPRESSION = re.compile(r"\$\{\{.*?\}\}")


@pytest.fixture(scope="module")
def workflow() -> dict[Any, Any]:
    return parse_workflow(load_workflow_text())


@pytest.fixture
def runner(tmp_path: Path) -> dict[str, Path]:
    """A runner temp dir whose factory checkout is this repository."""
    temp = tmp_path / "runner-temp"
    temp.mkdir()
    (temp / "factory").symlink_to(REPO_ROOT, target_is_directory=True)
    work = tmp_path / "work"
    work.mkdir()
    return {"temp": temp, "work": work, "root": tmp_path}


def stub_python(root: Path, exit_code: int = 0) -> tuple[Path, Path]:
    """A `python3` that records its argv as JSON lines and prints the plan marker."""
    bin_dir = root / "bin"
    bin_dir.mkdir()
    calls = root / "calls.jsonl"
    stub = bin_dir / "python3"
    stub.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        f"with open({str(calls)!r}, 'a', encoding='utf-8') as handle:\n"
        "    handle.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        f"print({PLAN_MARKER!r})\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return bin_dir, calls


def run_step(
    step: dict[str, Any], runner: dict[str, Path], env: dict[str, str], path_prefix: Path | None
) -> subprocess.CompletedProcess:
    # Expressions the runner would substitute; none of them is under test here.
    script = EXPRESSION.sub("owner/repo", str(step["run"]))
    full_env = {**os.environ, "RUNNER_TEMP": str(runner["temp"]), **env}
    if path_prefix is not None:
        full_env["PATH"] = f"{path_prefix}{os.pathsep}{full_env['PATH']}"
    return subprocess.run(  # noqa: S603
        ["bash", "-e", "-c", script],  # noqa: S607
        cwd=runner["work"],
        env=full_env,
        capture_output=True,
        text=True,
        check=False,
    )


def calls_of(calls: Path) -> list[list[str]]:
    return [json.loads(line) for line in calls.read_text(encoding="utf-8").splitlines()]


# --- skip_head_prefixes -------------------------------------------------------


def test_assess_exposes_the_skip_decision(workflow: dict[Any, Any]) -> None:
    job = job_named(workflow, "assess")
    assert (job.get("outputs") or {}).get("skip") == "${{ steps.skip.outputs.skip }}"
    step = next(step for step in steps_of(job) if step.get("id") == "skip")
    assert (step.get("env") or {}).get("PR_SKIP_HEAD_PREFIXES") == (
        "${{ inputs.skip_head_prefixes }}"
    )


@pytest.mark.parametrize(
    ("prefixes", "expected"), [("maintenance/", "true"), ("", "false"), ("x/, y/", "false")]
)
def test_the_skip_step_writes_the_output(
    workflow: dict[Any, Any], runner: dict[str, Path], prefixes: str, expected: str
) -> None:
    step = next(
        step for step in steps_of(job_named(workflow, "assess")) if step.get("id") == "skip"
    )
    (runner["work"] / "context.json").write_text(
        json.dumps({"head_ref": "maintenance/weekly"}), encoding="utf-8"
    )
    output = runner["root"] / "github_output"
    output.write_text("", encoding="utf-8")

    run = run_step(
        step, runner, {"GITHUB_OUTPUT": str(output), "PR_SKIP_HEAD_PREFIXES": prefixes}, None
    )

    assert run.returncode == 0, run.stderr
    assert output.read_text(encoding="utf-8").splitlines() == [f"skip={expected}"]


@pytest.mark.parametrize("name", ["review", "publish"])
def test_a_skipped_head_runs_neither_review_nor_publish(
    workflow: dict[Any, Any], name: str
) -> None:
    condition = normalize(job_named(workflow, name).get("if"))
    assert "needs.assess.outputs.skip != 'true'" in condition


def test_publish_rechecks_the_prefixes_on_its_fresh_fetch(workflow: dict[Any, Any]) -> None:
    env = job_env(workflow, "publish")
    assert env.get("PR_SKIP_HEAD_PREFIXES") == "${{ inputs.skip_head_prefixes }}"


# --- standards_path and setup_command -----------------------------------------


def review_step(workflow: dict[Any, Any]) -> dict[str, Any]:
    return step_running(job_named(workflow, "review"), "scripts/pr_review.py")


@pytest.mark.parametrize(
    ("standards", "expected"),
    [
        ("", []),
        ("docs/standards.md", ["--standards", "docs/standards.md"]),
        ("/home/runner/.claude/CLAUDE.md", ["--standards", "/home/runner/.claude/CLAUDE.md"]),
    ],
)
def test_standards_path_reaches_the_review_cli(
    workflow: dict[Any, Any], runner: dict[str, Path], standards: str, expected: list[str]
) -> None:
    step = review_step(workflow)
    assert (step.get("env") or {}).get("STANDARDS_PATH") == "${{ inputs.standards_path }}"
    bin_dir, calls = stub_python(runner["root"])

    run = run_step(step, runner, {"STANDARDS_PATH": standards}, bin_dir)

    assert run.returncode == 0, run.stderr
    [argv] = calls_of(calls)
    assert argv == [
        f"{runner['temp']}/factory/scripts/pr_review.py",
        "--context",
        "context.json",
        *expected,
    ]


def setup_step(workflow: dict[Any, Any]) -> dict[str, Any]:
    return step_running(job_named(workflow, "review"), "SETUP_COMMAND")


def test_the_setup_command_runs_only_when_set_and_before_claude_code(
    workflow: dict[Any, Any],
) -> None:
    step = setup_step(workflow)
    steps = steps_of(job_named(workflow, "review"))
    install = step_running(job_named(workflow, "review"), "@anthropic-ai/claude-code@")
    assert normalize(step.get("if")) == "inputs.setup_command != ''"
    assert (step.get("env") or {}) == {"SETUP_COMMAND": "${{ inputs.setup_command }}"}
    assert MODEL_KEY not in str(step), "the setup command never sees the model token"
    assert steps.index(step) < steps.index(install) < steps.index(review_step(workflow))


def test_the_setup_command_runs_in_the_callers_checkout_and_fails_the_job(
    workflow: dict[Any, Any], runner: dict[str, Path]
) -> None:
    step = setup_step(workflow)

    ok = run_step(step, runner, {"SETUP_COMMAND": "touch installed && echo done"}, None)
    failed = run_step(step, runner, {"SETUP_COMMAND": "false; touch not-reached"}, None)

    assert ok.returncode == 0, ok.stderr
    assert (runner["work"] / "installed").is_file()
    assert failed.returncode != 0, "a failed setup must stop the review"
    assert not (runner["work"] / "not-reached").exists()


# --- quiet_logs and fail_on_unavailable -----------------------------------------


def publish_step(workflow: dict[Any, Any]) -> dict[str, Any]:
    return step_running(job_named(workflow, "publish"), "scripts/pr_publish.py")


def run_publish(
    workflow: dict[Any, Any],
    runner: dict[str, Path],
    exit_code: int = 0,
    **env: str,
) -> tuple[subprocess.CompletedProcess, list[list[str]]]:
    bin_dir, calls = stub_python(runner["root"], exit_code)
    summary = runner["root"] / "summary.md"
    base = {
        "WRITE": "true",
        "PR": "7",
        "QUIET_LOGS": "false",
        "FAIL_ON_UNAVAILABLE": "false",
        "GITHUB_STEP_SUMMARY": str(summary),
        "RUN_URL": "https://example.invalid/run",
    }
    run = run_step(publish_step(workflow), runner, {**base, **env}, bin_dir)
    return run, calls_of(calls)


def test_the_publish_step_reads_both_switches_from_the_inputs(workflow: dict[Any, Any]) -> None:
    env = publish_step(workflow).get("env") or {}
    assert env.get("QUIET_LOGS") == "${{ inputs.quiet_logs }}"
    assert env.get("FAIL_ON_UNAVAILABLE") == "${{ inputs.fail_on_unavailable }}"


@pytest.mark.parametrize("write", ["true", "false"])
def test_by_default_the_plan_is_logged_and_no_switch_is_passed(
    workflow: dict[Any, Any], runner: dict[str, Path], write: str
) -> None:
    run, calls = run_publish(workflow, runner, WRITE=write)

    assert run.returncode == 0, run.stderr
    assert PLAN_MARKER in run.stdout, "without quiet_logs the plan is printed as before"
    [argv] = calls
    assert "--quiet" not in argv
    assert "--fail-on-unavailable" not in argv
    assert ("--write" in argv) is (write == "true")


@pytest.mark.parametrize("write", ["true", "false"])
def test_quiet_logs_keeps_the_plan_out_of_the_log(
    workflow: dict[Any, Any], runner: dict[str, Path], write: str
) -> None:
    run, calls = run_publish(workflow, runner, WRITE=write, QUIET_LOGS="true")

    assert run.returncode == 0, run.stderr
    assert PLAN_MARKER not in run.stdout + run.stderr
    [argv] = calls
    assert "--quiet" in argv, "the summary writer must leave out the plan JSON too"


@pytest.mark.parametrize("quiet", ["true", "false"])
def test_fail_on_unavailable_reaches_the_publisher_and_its_exit_code_fails_the_step(
    workflow: dict[Any, Any], runner: dict[str, Path], quiet: str
) -> None:
    run, calls = run_publish(
        workflow, runner, exit_code=8, FAIL_ON_UNAVAILABLE="true", QUIET_LOGS=quiet
    )

    assert run.returncode == 8
    [argv] = calls
    assert "--fail-on-unavailable" in argv
