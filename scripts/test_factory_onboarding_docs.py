"""The onboarding runbook and the check script stay in step with the factory workflows."""

from __future__ import annotations

from pathlib import Path

import factory_onboarding_check
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
RUNBOOK = (ROOT / "docs" / "agents" / "factory-onboarding.md").read_text(encoding="utf-8")
FACTORY_FILES = (
    "factory-implementer.yml",
    "factory-pr-review.yml",
    "factory-issue-triage.yml",
    "factory-triage-label.yml",
)


def workflow_call(name: str) -> dict:
    document = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    # PyYAML reads the bare key `on` as the boolean True.
    triggers = document.get("on", document.get(True))
    return triggers["workflow_call"] or {}


def required(block: dict | None) -> tuple[str, ...]:
    return tuple(name for name, spec in (block or {}).items() if (spec or {}).get("required"))


@pytest.mark.parametrize("name", FACTORY_FILES)
def test_runbook_names_every_input_and_secret(name):
    call = workflow_call(name)
    names = [*(call.get("inputs") or {}), *(call.get("secrets") or {})]

    absent = [item for item in names if f"`{item}`" not in RUNBOOK]
    assert absent == [], f"{name}: {absent}"


def test_requirements_constant_matches_the_workflow_files():
    from_files = {
        name: {
            "inputs": required(workflow_call(name).get("inputs")),
            "secrets": required(workflow_call(name).get("secrets")),
        }
        for name in FACTORY_FILES
    }

    assert factory_onboarding_check.REQUIREMENTS == from_files


def test_runbook_has_its_sections_and_links():
    for heading in (
        "## Before you start",
        "## Caller templates",
        "## Inputs and secret",
        "## One SHA for all callers",
        "## Manual steps, in order",
        "## Start slow",
        "## First implementer run probes the token's rights",
        "## Rollback",
        "## Cost",
    ):
        assert heading in RUNBOOK, heading
    for link in (
        "../adr/0018-reusable-factory-workflows.md",
        "https://github.com/fabiandistler/agents/issues/789",
        "https://docs.github.com/en/billing/concepts/product-billing/github-actions",
        "scripts/factory_onboarding_check.py",
    ):
        assert link in RUNBOOK, link


def test_runbook_templates_pin_and_pass_the_secret_by_name():
    for name in FACTORY_FILES:
        assert f"fabiandistler/agents/.github/workflows/{name}@<SHA> # <date>" in RUNBOOK
    assert "secrets: inherit`" in RUNBOOK
    assert "\n    secrets: inherit" not in RUNBOOK
    assert RUNBOOK.count("\npermissions: {}\n") == len(FACTORY_FILES)
    assert "statuses: write" in RUNBOOK


def test_runbook_templates_pass_the_check():
    blocks = RUNBOOK.split("```yaml\n")[1:]
    # A filled-in template pins a real SHA; `<SHA>` is the placeholder.
    templates = [block.split("```", 1)[0].replace("<SHA>", "a" * 40) for block in blocks]
    callers = {}
    for template in templates:
        for line in template.splitlines():
            match = factory_onboarding_check.USES_LINE.match(line)
            if match:
                callers[match["file"]] = factory_onboarding_check.Caller(
                    "x.yml", match["ref"], template
                )

    assert sorted(callers) == sorted(FACTORY_FILES)
    for name, caller in callers.items():
        status, _, detail = factory_onboarding_check.caller_line(name, caller, "main")
        assert status == "OK", detail


def test_reusable_workflow_doc_links_the_runbook():
    text = (ROOT / "docs" / "agents" / "pr-review-reusable-workflow.md").read_text(encoding="utf-8")

    assert "(factory-onboarding.md)" in text
