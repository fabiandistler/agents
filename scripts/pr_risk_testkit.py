"""Shared context builders for the risk policy tests (test_pr_risk*.py).

The contexts are plain dictionaries in the shape ``pr_github.py`` emits.
``file_entry`` is reused by the publish testkit.
"""

from __future__ import annotations


def file_entry(
    path: str,
    *,
    status: str = "modified",
    additions: int = 1,
    deletions: int = 0,
    binary: bool = False,
    renamed_from: str | None = None,
) -> dict:
    return {
        "path": path,
        "status": status,
        "additions": additions,
        "deletions": deletions,
        "binary": binary,
        "renamed_from": renamed_from,
    }


def make_context(files: list[dict] | None = None, **overrides: object) -> dict:
    context = {
        "schema_version": 1,
        "repo": "fabiandistler/agents",
        "number": 42,
        "title": "A change",
        "body": "",
        "author": "fabiandistler",
        "head_sha": "abc123",
        "head_ref": "fix/x",
        "base_ref": "main",
        "default_branch": "main",
        "draft": False,
        "fork": False,
        "mergeable": True,
        "labels": [],
        "files": [file_entry("docs/guide.md")] if files is None else files,
        "diff": "",
        "diff_status": "complete",
        "base_files": {},
        "comments": [],
        "reviews": {"changes_requested": False},
    }
    context.update(overrides)
    return context
