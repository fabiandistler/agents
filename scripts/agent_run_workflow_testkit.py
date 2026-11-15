"""Shared loaders and accessors for the agent-run workflow structure tests.

The tests in test_agent_run_workflows.py and
test_factory_implementer_workflow.py read the agent-run workflow files
(.github/workflows/) through these helpers, so each safety property can be
asserted on its own.
"""

from __future__ import annotations

import re
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
