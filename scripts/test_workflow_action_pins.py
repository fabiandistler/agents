"""Every action a workflow runs is pinned to a full commit SHA.

A tag such as `@v1` can be moved to new code; a full commit SHA cannot. A moved
tag would run unreviewed code next to the job's token and secrets, so every
`uses:` in every workflow names a 40-hex commit with its release tag as a
trailing `# vX.Y.Z` comment, which keeps the pin readable and updatable.
Local actions (`./path`) are the repo's own reviewed code and are exempt.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
WORKFLOW_FILES = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])

# `uses:` as a step key or a reusable-workflow job key; YAML drops the
# trailing comment, so the check reads the raw text.
USES = re.compile(r"^\s*(?:-\s+)?uses:\s*(?P<ref>\S+)(?P<rest>.*)$")
PINNED = re.compile(r"[\w.-]+/[\w./-]+@(?P<sha>[0-9a-f]{40})")
TAG_COMMENT = re.compile(r"\s+# v\d+(?:\.\d+)*$")


def _uses_lines(path: Path) -> list[tuple[int, str, str]]:
    found = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = USES.match(line)
        if match and not match["ref"].startswith("./"):
            found.append((number, match["ref"].strip("'\""), match["rest"]))
    return found


def test_the_check_sees_the_workflows() -> None:
    assert WORKFLOW_FILES, f"no workflow files under {WORKFLOWS}; the pin check would be vacuous"
    assert any(_uses_lines(path) for path in WORKFLOW_FILES)


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_commit_sha_with_its_tag(path: Path) -> None:
    unpinned = [
        f"{path.name}:{number}: {ref}{rest}"
        for number, ref, rest in _uses_lines(path)
        if not PINNED.fullmatch(ref) or not TAG_COMMENT.fullmatch(rest)
    ]
    assert not unpinned, (
        "pin every action to a full commit SHA with its tag as a trailing "
        f"`# vX.Y.Z` comment: {unpinned}"
    )


def test_one_tag_maps_to_one_commit_across_workflows() -> None:
    # The same release pinned to two commits means one pin was typed by hand
    # or one bump missed a file.
    commits: dict[tuple[str, str], set[str]] = {}
    for path in WORKFLOW_FILES:
        for _, ref, rest in _uses_lines(path):
            action, _, sha = ref.partition("@")
            commits.setdefault((action, rest.strip()), set()).add(sha)
    conflicting = {
        f"{action} {tag}": shas for (action, tag), shas in commits.items() if len(shas) > 1
    }
    assert not conflicting, f"one release tag pinned to several commits: {conflicting}"
