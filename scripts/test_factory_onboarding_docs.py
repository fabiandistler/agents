"""The onboarding runbook and the check script stay in step with the factory workflows."""

from __future__ import annotations

from pathlib import Path

import factory_onboarding_check
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
RUNBOOK = (ROOT / "docs" / "agents" / "factory-onboarding.md").read_text(encoding="utf-8")
INPUTS = (ROOT / "docs" / "agents" / "factory-inputs.md").read_text(encoding="utf-8")
FACTORY_FILES = (
    "factory-implementer.yml",
    "factory-implementer-queue.yml",
    "factory-pr-review.yml",
    "factory-issue-triage.yml",
    "factory-triage-label.yml",
    "factory-rework.yml",
    "factory-fix-task.yml",
)


def workflow_call(name: str) -> dict:
    document = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    # PyYAML reads the bare key `on` as the boolean True.
    triggers = document.get("on", document.get(True))
    return triggers["workflow_call"] or {}


def required(block: dict | None) -> tuple[str, ...]:
    return tuple(name for name, spec in (block or {}).items() if (spec or {}).get("required"))


@pytest.mark.parametrize("name", FACTORY_FILES)
def test_inputs_page_names_every_input_and_secret(name):
    call = workflow_call(name)
    names = [*(call.get("inputs") or {}), *(call.get("secrets") or {})]

    assert f"`{name}`" in INPUTS
    absent = [item for item in names if f"`{item}`" not in INPUTS]
    assert absent == [], f"{name}: {absent}"


def test_runbook_and_inputs_page_link_each_other():
    assert "[factory workflow inputs](factory-inputs.md)" in RUNBOOK
    assert "(factory-onboarding.md#caller-templates)" in INPUTS


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


def template_blocks() -> list[str]:
    # A filled-in template pins a real SHA; `<SHA>` is the placeholder.
    return [
        block.split("```", 1)[0].replace("<SHA>", "a" * 40)
        for block in RUNBOOK.split("```yaml\n")[1:]
    ]


def test_runbook_templates_pin_and_pass_the_secret_by_name():
    for name in FACTORY_FILES:
        assert (
            f"fabiandistler/agents/.github/workflows/{name}@<SHA> # agents main, <date>\n"
            in RUNBOOK
        )
    assert "secrets: inherit`" in RUNBOOK
    assert "\n    secrets: inherit" not in RUNBOOK
    assert RUNBOOK.count("\npermissions: {}\n") == len(FACTORY_FILES)
    assert "statuses: write" in RUNBOOK


def test_no_template_pin_has_a_one_word_comment():
    # zizmor's online ref-version-mismatch audit reads a one-word comment after
    # a SHA as a version and flags it.
    pins = [
        line
        for block in template_blocks()
        for line in block.splitlines()
        if factory_onboarding_check.USES_LINE.match(line)
    ]

    assert len(pins) == len(FACTORY_FILES)
    for line in pins:
        _, _, comment = line.partition(" # ")
        assert len(comment.split()) > 1, line


def test_triage_template_has_no_issue_comment_trigger():
    triage = next(block for block in template_blocks() if "name: issue-triage\n" in block)
    triggers = yaml.safe_load(triage)[True]

    assert "issue_comment" not in triggers
    assert "re-adds `needs-triage`" in RUNBOOK


def test_runbook_templates_pass_the_check():
    callers = {}
    for template in template_blocks():
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


def template_for(name: str) -> dict:
    (block,) = [b for b in template_blocks() if f"/{name}@" in b]
    return yaml.safe_load(block)


def local_caller(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("factory_file", "caller_file"),
    [
        ("factory-implementer.yml", "implementer.yml"),
        ("factory-implementer-queue.yml", "implementer-queue.yml"),
        ("factory-pr-review.yml", "pr-review.yml"),
        ("factory-issue-triage.yml", "issue-triage.yml"),
        ("factory-rework.yml", "rework.yml"),
        ("factory-fix-task.yml", "fix-task.yml"),
    ],
)
def test_template_matches_this_repositorys_caller(factory_file, caller_file):
    template, local = template_for(factory_file), local_caller(caller_file)
    assert template["name"] == local["name"]
    (template_job,) = template["jobs"].values()
    (local_job,) = local["jobs"].values()
    assert template_job["permissions"] == local_job["permissions"]
    # The triage template drops `issue_comment` on purpose (see the runbook).
    assert set(template[True]) <= set(local[True])
    if factory_file != "factory-fix-task.yml":
        assert template[True].get("workflow_run") == local[True].get("workflow_run")


def test_implementer_template_names_the_queue_template_that_follows_it():
    implementer = template_for("factory-implementer.yml")
    queue = template_for("factory-implementer-queue.yml")
    (job,) = implementer["jobs"].values()
    assert job["with"]["queue_workflow"] == "implementer-queue.yml"
    assert job["with"]["fix_task_workflow"] == "fix-task.yml"
    assert queue["name"] == "implementer-queue"
    assert queue[True]["workflow_run"]["workflows"] == [implementer["name"]]
    (queue_job,) = queue["jobs"].values()
    assert queue_job["with"]["fix_task_workflow"] == "fix-task.yml"


def test_rework_template_follows_the_pr_review_template():
    review = template_for("factory-pr-review.yml")
    assert template_for("factory-rework.yml")[True]["workflow_run"]["workflows"] == [review["name"]]


def test_fix_template_watches_only_the_targets_callers_that_the_policy_files():
    import factory_failure_policy

    watched = template_for("factory-fix-task.yml")[True]["workflow_run"]["workflows"]
    templates = {
        template_for(name)["name"]: name
        for name in FACTORY_FILES
        if name not in ("factory-fix-task.yml", "factory-triage-label.yml")
    }
    assert sorted(watched) == sorted(templates), "every watched caller has a template"
    for name in watched:
        path = f".github/workflows/{name}.yml"
        assert path in factory_failure_policy.WATCHED_WORKFLOWS, path
    assert "fix-task" not in watched
