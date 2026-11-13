"""Guardrails for .github/workflows/claude.yml, the `@claude` mention assistant.

Every trigger type creates a workflow run per event, even when the job `if`
skips it, so the workflow listens only to events a mention can arrive in (#797).
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "claude.yml"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_listens_only_to_comments_and_reviews():
    # PyYAML reads the bare `on` key as boolean True.
    assert _workflow()[True] == {
        "issue_comment": {"types": ["created"]},
        "pull_request_review_comment": {"types": ["created"]},
        "pull_request_review": {"types": ["submitted"]},
    }


def test_job_if_covers_exactly_the_triggers():
    condition = _workflow()["jobs"]["claude"]["if"]
    for event in _workflow()[True]:
        assert f"github.event_name == '{event}'" in condition, event
    assert "github.event_name == 'issues'" not in condition
