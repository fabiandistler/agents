"""Shared loaders and accessors for the agent-run workflow structure tests.

The tests in test_agent_run_workflows.py read the agent-run workflow files
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
SKILL_AUDIT = WORKFLOWS / "skill-audit.yml"

ACTION = "anthropics/claude-code-action@"
SHA_PIN = re.compile(r"^anthropics/claude-code-action@[0-9a-f]{40}$")
EXPRESSION = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")


def workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def single_job(path: Path) -> dict:
    jobs = workflow(path)["jobs"]
    assert len(jobs) == 1, f"{path.name} should have one job"
    return next(iter(jobs.values()))


def model_step(job: dict) -> dict:
    steps = [step for step in job["steps"] if step.get("uses", "").startswith(ACTION)]
    assert len(steps) == 1, "exactly one claude-code-action step"
    return steps[0]


def report_step(job: dict) -> dict:
    steps = [step for step in job["steps"] if step.get("name") == "Report the run"]
    assert len(steps) == 1, "exactly one report step"
    return steps[0]
