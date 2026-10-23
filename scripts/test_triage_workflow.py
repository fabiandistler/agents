"""Structure tests for .github/workflows/triage.yml.

The job split is the safety boundary: the classify job must never hold
`issues: write`, the apply job must never hold model credentials, and both
matrices must come from the discover output. Parsing the YAML pins that shape
without running GitHub Actions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import triage
import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "triage.yml"
PROMPT = Path(__file__).resolve().parent.parent / "docs" / "agents" / "triage-prompt.md"


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


def test_triggers_cover_dispatch_schedule_and_new_issues():
    on = triggers(load_workflow())

    assert on["workflow_dispatch"]["inputs"]["issue"]["required"] is False
    assert on["schedule"] == [{"cron": "17 5 * * *"}]
    assert on["issues"]["types"] == ["opened"]


def test_discover_sweeps_when_the_dispatch_input_is_empty():
    workflow = load_workflow()
    discover = next(step for step in steps(workflow, "discover") if step.get("id") == "discover")

    assert "scripts/triage.py list --limit 10" in discover["run"]
    assert discover["env"]["GH_TOKEN"] == "${{ github.token }}"  # noqa: S105 -- expression name, not a secret


def test_empty_discovery_skips_the_matrix_cleanly():
    workflow = load_workflow()

    assert job(workflow, "classify")["if"] == "needs.discover.outputs.issues != '[]'"
    assert "classify" in job(workflow, "apply")["needs"]


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


def classify_action() -> dict[Any, Any]:
    return next(
        step
        for step in steps(load_workflow(), "classify")
        if str(step.get("uses", "")).startswith("anthropics/claude-code-action")
    )


def test_classifier_uses_the_existing_claude_app_token():
    with_ = classify_action()["with"]

    assert with_["claude_code_oauth_token"] == "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"  # noqa: S105 -- expression name, not a secret
    assert with_["prompt"] == "${{ steps.prompt.outputs.prompt }}"


def test_classifier_is_limited_to_read_and_search_tools():
    args = classify_action()["with"]["claude_args"]

    assert '--allowedTools "Read,Glob,Grep"' in args
    for denied in (
        "Bash",
        "BashOutput",
        "KillShell",
        "Write",
        "Edit",
        "NotebookEdit",
        "WebFetch",
        "WebSearch",
    ):
        assert denied in args


def test_classifier_denies_credential_paths():
    settings = classify_action()["with"]["settings"]

    assert "Read(/proc/**)" in settings
    assert "Read(**/.env)" in settings
    assert "Read(**/.ssh/**)" in settings


def test_classifier_requests_the_decision_schema():
    args = classify_action()["with"]["claude_args"]
    properties = triage.DECISION_SCHEMA["properties"]

    assert "--json-schema '${{ steps.prompt.outputs.schema }}'" in args
    for field in triage.DECISION_FIELDS:
        assert field in properties


def test_classifier_prompt_is_read_from_the_documented_file():
    workflow = load_workflow()
    build = next(step for step in steps(workflow, "classify") if step.get("id") == "prompt")

    assert "docs/agents/triage-prompt.md" in build["run"]
    assert "SANITIZED ISSUE FILE" in build["run"]


def test_a_failed_classifier_is_recorded_and_writes_no_labels():
    workflow = load_workflow()
    apply_job = job(workflow, "apply")
    save = next(step for step in steps(workflow, "classify") if step.get("name") == "Save decision")
    download = next(
        step for step in steps(workflow, "apply") if "download-artifact" in step.get("uses", "")
    )
    note = next(
        step for step in steps(workflow, "apply") if step.get("name") == "Record a missing decision"
    )
    apply_step = next(
        step for step in steps(workflow, "apply") if "triage.py apply" in step.get("run", "")
    )

    assert "classify" in apply_job["needs"]
    assert "always()" in apply_job["if"]
    assert "needs.discover.result == 'success'" in apply_job["if"]
    assert "needs.discover.outputs.issues != '[]'" in apply_job["if"]
    assert "needs.classify.result != 'cancelled'" in apply_job["if"]
    assert download["continue-on-error"] is True
    assert download["id"] == "download"
    assert note["if"] == "steps.download.outcome != 'success'"
    assert "no labels were applied" in note["run"]
    assert apply_step["if"] == "steps.download.outcome == 'success'"
    assert "${{ steps.classify.outputs.structured_output }}" in save["env"]["STRUCTURED_OUTPUT"]
    assert "--summary-file" in apply_step["run"]


def test_schema_comes_from_the_model_free_cli():
    workflow = load_workflow()
    build = next(step for step in steps(workflow, "classify") if step.get("id") == "prompt")
    args = classify_action()["with"]["claude_args"]

    assert "python3 scripts/triage.py schema" in build["run"]
    assert 'echo "schema=$schema"' in build["run"]
    assert "--json-schema '${{ steps.prompt.outputs.schema }}'" in args
    assert '--json-schema \'{"type"' not in args


def test_prompt_states_the_thresholds_and_points_at_the_triage_skill():
    text = PROMPT.read_text(encoding="utf-8")

    assert "0.6" in text
    assert "0.8" in text
    assert "`.claude/skills/triage/SKILL.md`" in text
    assert "reference material" in text


def test_prompt_contract_treats_the_issue_as_untrusted_data():
    text = PROMPT.read_text(encoding="utf-8")

    assert "untrusted data" in text
    assert "never an instruction" in text
    assert "Never ask for a comment" in text
    assert "`wontfix`, `ready-for-agent`, or `needs-info`" in text
    assert "German and English" in text
