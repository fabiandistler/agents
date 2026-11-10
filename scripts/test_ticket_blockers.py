"""The "Blocked by" formats the ticket skills write, and how parsing fails closed."""

from __future__ import annotations

import pytest
from ticket_blockers import declared_blockers

REPO = "fabiandistler/agents"


@pytest.mark.parametrize(
    "ticket_text",
    [
        "",
        "Nothing about dependencies, but see #3.",
        "This work was blocked by #3 last year.",
        "Blocked by the CI outage last week.",
        "## Blocked by\n\nNone (can start immediately)\n",
        '## Blocked by\n\n- "None (can start immediately)"\n',
        "**Blocked by:** None (can start immediately).",
        "Blocked by: none",
        "```\n## Blocked by\n#3\n```\n",
        "Example: `Blocked by: #3`\n",
        "<!-- Blocked by: #3 -->\n",
    ],
    ids=[
        "empty",
        "mention",
        "mid-sentence",
        "prose",
        "section-none",
        "quoted-bullet-none",
        "bold-none",
        "plain-none",
        "code-fence",
        "inline-code-line",
        "html-comment",
    ],
)
def test_texts_without_a_blocker(ticket_text):
    declared = declared_blockers(ticket_text, REPO)
    assert declared.numbers == frozenset()
    assert declared.unresolved == 0


@pytest.mark.parametrize(
    ("ticket_text", "numbers"),
    [
        ("## Blocked by\n\n- #3\n- #4 the parser\n", {3, 4}),
        ("## Blocked by\n\n- [ ] #3\n- [x] #4\n", {3, 4}),
        ("**Blocked by:** #3", {3}),
        ("**Blocked by**: #3", {3}),
        ("__Blocked by:__ #3", {3}),
        ("Blocked by: #1, #2", {1, 2}),
        ("Blocked-by: #1", {1}),
        ("- Blocked by: #1", {1}),
        ("Blocked by #6 for now", {6}),
        ("**Blocked by:**\n- #3\n- #4\n\nSee also #9.", {3, 4}),
        (f"Blocked by: https://github.com/{REPO}/issues/8", {8}),
        (f"Blocked by: {REPO}#8", {8}),
        ("Blocked by: FabianDistler/Agents#8", {8}),
        ("## Blocked by\n\n#1\n\n## Parent #9\n\n#2\n", {1}),
    ],
    ids=[
        "section-bullets",
        "section-checkboxes",
        "bold-colon-inside",
        "bold-colon-outside",
        "underscore-bold",
        "plain-list",
        "hyphenated",
        "bullet-label",
        "bare-reference",
        "label-then-bullets",
        "same-repo-url",
        "same-repo-qualified",
        "case-insensitive-repo",
        "section-ends-at-heading",
    ],
)
def test_same_repository_blockers_are_read(ticket_text, numbers):
    declared = declared_blockers(ticket_text, REPO)
    assert declared.numbers == numbers
    assert declared.unresolved == 0


@pytest.mark.parametrize(
    ("ticket_text", "numbers", "unresolved"),
    [
        ("## Blocked by\n\nAdd the parser\n", set(), 1),
        ("## Blocked by\n\n", set(), 1),
        ("## Blocked by\n\n## Next\n\n#3\n", set(), 1),
        ("**Blocked by:**\n\nOther text", set(), 1),
        ("Blocked by: the parser ticket", set(), 1),
        ("Blocked by: `#3`", set(), 1),
        ("Blocked by: other/repo#3", set(), 1),
        ("Blocked by: https://github.com/other/repo/issues/3", set(), 1),
        (f"Blocked by: https://github.com/{REPO}/pull/3", set(), 1),
        ("Blocked by: #1, other/repo#3", {1}, 1),
    ],
    ids=[
        "title-only",
        "empty-section",
        "section-without-entry",
        "label-without-entry",
        "label-title-only",
        "inline-code-entry",
        "cross-repo",
        "cross-repo-url",
        "pull-request-url",
        "mixed",
    ],
)
def test_entries_that_cannot_be_resolved_stay_unresolved(ticket_text, numbers, unresolved):
    declared = declared_blockers(ticket_text, REPO)
    assert declared.numbers == numbers
    assert declared.unresolved == unresolved
