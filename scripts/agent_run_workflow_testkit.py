"""Shared loaders and accessors for the agent-run workflow structure tests.

The tests in test_agent_run_workflows.py and
test_factory_implementer_workflow.py read the agent-run workflow files
(.github/workflows/) through these helpers, so each safety property can be
asserted on its own. Tests that run a workflow step through bash take its
PATH from step_path().
"""

from __future__ import annotations

import atexit
import functools
import os
import re
import shlex
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
IMPLEMENTER = WORKFLOWS / "implementer.yml"
FACTORY_IMPLEMENTER = WORKFLOWS / "factory-implementer.yml"
SKILL_AUDIT = WORKFLOWS / "skill-audit.yml"
# The Rework jobs live in the reusable file; rework.yml is its thin caller.
REWORK = WORKFLOWS / "factory-rework.yml"
RETRO = WORKFLOWS / "retro.yml"

ACTION = "anthropics/claude-code-action@"
SHA_PIN = re.compile(r"^anthropics/claude-code-action@[0-9a-f]{40}$")
EXPRESSION = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")


def workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def single_job(path: Path) -> dict:
    jobs = workflow(path)["jobs"]
    assert len(jobs) == 1, f"{path.name} should have one job"
    return next(iter(jobs.values()))


def agent_job(path: Path) -> dict:
    """The workflow's only job, or of several the one that runs the model.

    factory-implementer.yml adds a model-free follow-up job after its model job
    (#863); every other agent-run workflow has one job.
    """
    jobs = workflow(path)["jobs"]
    if len(jobs) == 1:
        return next(iter(jobs.values()))
    with_model = [
        job
        for job in jobs.values()
        if any(step.get("uses", "").startswith(ACTION) for step in job.get("steps", []))
    ]
    assert len(with_model) == 1, f"{path.name} should have exactly one model job"
    return with_model[0]


def model_step(job: dict) -> dict:
    steps = [step for step in job["steps"] if step.get("uses", "").startswith(ACTION)]
    assert len(steps) == 1, "exactly one claude-code-action step"
    return steps[0]


def report_step(job: dict) -> dict:
    steps = [step for step in job["steps"] if step.get("name") == "Report the run"]
    assert len(steps) == 1, "exactly one report step"
    return steps[0]


def checkouts(job: dict) -> list[dict]:
    return [step for step in job["steps"] if "actions/checkout@" in step.get("uses", "")]


def step_with_id(job: dict, step_id: str) -> dict:
    steps = [step for step in job["steps"] if step.get("id") == step_id]
    assert len(steps) == 1, f"exactly one step with id {step_id!r}"
    return steps[0]


def named_step(job: dict, name: str) -> dict:
    steps = [step for step in job["steps"] if step.get("name") == name]
    assert len(steps) == 1, f"exactly one step named {name!r}"
    return steps[0]


def step_path() -> str:
    """PATH for a workflow step run through bash, with the test interpreter as python3.

    The steps call a bare python3 and the repo scripts need CI's 3.12, so a
    pytest run on 3.12 must not hand them an older system python3 (#1038).
    """
    return f"{_test_interpreter_dir()}{os.pathsep}{os.environ['PATH']}"


@functools.cache
def _test_interpreter_dir() -> str:
    # Not dirname(sys.executable): that directory may hold only python3.12,
    # and a venv's bin/ would shadow unrelated tools. Not a symlink either:
    # Python finds pyvenv.cfg next to the path it was started by, so a
    # symlinked venv interpreter would run without the venv's packages.
    directory = tempfile.mkdtemp(prefix="step-python-")
    atexit.register(shutil.rmtree, directory, ignore_errors=True)
    shim = Path(directory) / "python3"
    shim.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$@"\n', encoding="utf-8")
    shim.chmod(0o755)
    return directory
