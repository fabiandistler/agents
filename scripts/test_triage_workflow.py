"""Structure tests for .github/workflows/triage.yml.

The job split is the safety boundary: the classify job must never hold
`issues: write`, the apply job must never hold model credentials, and both
matrices must come from the discover output. Parsing the YAML pins that shape
without running GitHub Actions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "triage.yml"


def load_workflow() -> dict[Any, Any]:
    # PyYAML reads the unquoted `on:` key as boolean True (YAML 1.1).
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def triggers(workflow: dict[Any, Any]) -> dict[Any, Any]:
    on = workflow.get("on") or workflow.get(True)
    assert isinstance(on, dict)
    return on


def job(workflow: dict[Any, Any], name: str) -> dict[Any, Any]:
    return workflow["jobs"][name]


def steps(workflow: dict[Any, Any], name: str) -> list[dict[Any, Any]]:
    return job(workflow, name)["steps"]


def test_triggers_cover_dispatch_and_new_issues():
    on = triggers(load_workflow())

    assert on["workflow_dispatch"]["inputs"]["issue"]["required"] is True
    assert on["issues"]["types"] == ["opened"]


def test_top_level_permissions_are_empty():
    assert load_workflow()["permissions"] == {}


def test_classify_job_is_read_only_for_issues():
    permissions = job(load_workflow(), "classify")["permissions"]

    assert permissions["issues"] == "read"
    assert "write" not in permissions.values()


def test_apply_job_may_write_issues():
    permissions = job(load_workflow(), "apply")["permissions"]

    assert permissions["issues"] == "write"
    assert permissions["contents"] == "read"


def test_apply_job_has_no_model_credentials():
    workflow = load_workflow()
    rendered = yaml.safe_dump(job(workflow, "apply"), sort_keys=False)

    assert "secrets." not in rendered
    assert "claude-code-action" not in rendered


def test_matrices_come_from_the_discover_output():
    workflow = load_workflow()
    source = "${{ fromJSON(needs.discover.outputs.issues) }}"

    for name in ("classify", "apply"):
        assert job(workflow, name)["strategy"]["matrix"]["issue"] == source
        assert job(workflow, name)["strategy"]["max-parallel"] == 2
        assert job(workflow, name)["strategy"]["fail-fast"] is False


def test_artifact_handoff_uses_matching_names():
    workflow = load_workflow()
    upload = next(
        step for step in steps(workflow, "classify") if "upload-artifact" in step.get("uses", "")
    )
    download = next(
        step for step in steps(workflow, "apply") if "download-artifact" in step.get("uses", "")
    )

    assert upload["with"]["name"] == "triage-decision-${{ matrix.issue }}"
    assert download["with"]["name"] == upload["with"]["name"]


def test_fetch_and_apply_run_the_model_free_cli():
    workflow = load_workflow()
    fetch = "\n".join(step.get("run", "") for step in steps(workflow, "classify"))
    apply = "\n".join(step.get("run", "") for step in steps(workflow, "apply"))

    assert "scripts/triage.py fetch" in fetch
    assert "scripts/triage.py apply" in apply
    assert "$GITHUB_STEP_SUMMARY" in apply
