"""Shared builders for the review tests (test_pr_review*.py).

The context mirrors what ``pr_github.py`` emits; ``run_cli`` runs
``pr_review.py`` with the provider environment cleared, so no test calls a model.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "pr_review.py"
PROMPT = Path(__file__).resolve().parent / "pr_review_prompt.md"

VALID_RESPONSE = """\
RISK: medium
VERDICT: concerns
SUMMARY: The documentation change is useful but one heading no
longer matches the file it describes.

FINDINGS:
- docs/review.md:12 [warning] The heading is stale | fix: Rename the heading
* scripts/example.py [info] Minor wording | fix: Reflow the sentence
- docs/review.md:20 [blocker] The link target is missing
END
"""


def base_context(**overrides: object) -> dict:
    context = {
        "schema_version": 1,
        "repo": "fabiandistler/agents",
        "number": 42,
        "title": "Document the review bot",
        "body": "A short body.",
        "author": "fabiandistler",
        "head_sha": "abc123",
        "head_ref": "feat/x",
        "base_ref": "main",
        "default_branch": "main",
        "draft": False,
        "fork": False,
        "mergeable": True,
        "labels": [],
        "files": [
            {
                "path": "docs/review.md",
                "status": "modified",
                "additions": 3,
                "deletions": 1,
                "binary": False,
                "renamed_from": None,
            }
        ],
        "diff": "diff --git a/docs/review.md b/docs/review.md\n+New line\n",
        "diff_status": "complete",
        "base_files": {"docs/review.md": "Old line\n"},
        "base_paths": ["README.md", "docs/review.md", "scripts/tool.py"],
        "base_paths_truncated": False,
        "comments": [],
        "reviews": {"changes_requested": False},
    }
    context.update(overrides)
    return context


# A stand-in for the subscription token; tests check that it is never echoed.
FAKE_TOKEN = "sk-test-secret-value"  # noqa: S105


def recording_transport(calls: list[dict], response: str = VALID_RESPONSE):
    def transport(request: dict) -> str:
        calls.append(request)
        return response

    return transport


def user_payload(request: dict) -> str:
    return request["messages"][1]["content"]


def run_cli(*args: str, **env: str) -> subprocess.CompletedProcess:
    clean_env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"CLAUDE_CODE_OAUTH_TOKEN", "PR_REVIEW_MODEL"}
    }
    clean_env.update(env)
    return subprocess.run(  # noqa: S603 -- test invokes its own script with argv, no shell.
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=clean_env,
        check=False,
    )


def write_context(tmp_path: Path, context: dict) -> Path:
    path = tmp_path / "context.json"
    path.write_text(json.dumps(context), encoding="utf-8")
    return path


def dry_run_request(tmp_path: Path, context: dict, **env: str) -> dict:
    output = tmp_path / "request.json"
    run = run_cli(
        "--context",
        str(write_context(tmp_path, context)),
        "--dry-run",
        "--output",
        str(output),
        **env,
    )
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["output"] == str(output)
    return json.loads(output.read_text(encoding="utf-8"))
