"""The Retro PR body format in docs/agents/retro.md passes the PR issue-link check.

A Retro pull request closes no issue (ADR-0017). Its body must state that with
a `No issue` line and must hold no closing keyword before an issue reference,
or GitHub closes that issue on merge.
"""

from __future__ import annotations

import re
from pathlib import Path

from check_pr_issue_links import closing_references, issue_link_errors

REPO = "fabiandistler/agents"
RUNBOOK = Path(__file__).resolve().parent.parent / "docs" / "agents" / "retro.md"
TEMPLATE = re.compile(
    r"<!-- retro-pr-body:start -->\n```markdown\n(.*?)```\n<!-- retro-pr-body:end -->", re.DOTALL
)


def template() -> str:
    match = TEMPLATE.search(RUNBOOK.read_text(encoding="utf-8"))
    assert match, "docs/agents/retro.md lost its fenced PR body template"
    return match.group(1)


def filled_body() -> str:
    return (
        template()
        .replace("<pr>", "795")
        .replace(
            "<file: what changed>",
            "scripts/pr_review_prompt.md: flag closing keywords in quoted lines",
        )
        .replace("<category from the retro skill>", "Coding standards")
        .replace(
            "<link to the comment, review or commit>",
            "https://github.com/fabiandistler/agents/pull/795#issuecomment-1",
        )
        .replace(
            "<text for the maintainer to apply to .github/workflows/>",
            "Quote the three tasks without numbers: the Fix task (#783), the Rework task (#782).",
        )
        .replace("<text for mattpocock/skills>", "None.")
    )


def test_template_opens_with_the_no_issue_line():
    first = template().splitlines()[0]
    assert re.fullmatch(r"No issue: .+\. Refs #<pr>", first)


def test_template_has_the_required_sections():
    body = template()
    assert "| Change | Category | Evidence |" in body
    assert "## Proposed workflow-prompt changes" in body
    assert "## Proposed upstream changes to vendored guidance" in body


def test_filled_body_passes_the_issue_link_check():
    body = filled_body()
    assert issue_link_errors(body, REPO, set(), default_base=True) == []
    assert closing_references(body, REPO) == set()


def test_check_would_catch_a_closing_keyword_in_a_retro_body():
    """Guards the test above: the check does see a keyword before a number."""
    body = filled_body() + "\n> The three tasks: Fixes #783.\n"
    assert closing_references(body, REPO) == {f"{REPO}#783"}
    assert issue_link_errors(body, REPO, set(), default_base=True)
