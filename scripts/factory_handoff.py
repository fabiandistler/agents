"""The handoff protocol: the facts factory runs hand each other through GitHub.

A runner keeps nothing, so one run tells the next what happened through
comment and issue markers, run names, workflow file names and issue state
labels on GitHub (docs/factory/architecture.md, "Data flow"). This module owns
those facts: who counts as the factory's own author, the text of each marker,
the implementer run name, the agent branch name, the caller workflow file names
and the issue state labels every task moves (docs/agents/triage-labels.md).
``format_marker`` writes a marker; ``read_markers`` reads them back, and only
from entries the workflow bot wrote, so a marker a person quotes is just text.

Pure and standard library only; it imports no other factory module. The
marker texts, the run name, the agent branch and the state labels are a
contract with comments, issues and runs already stored on GitHub: a changed
byte resets a counter, duplicates a comment or loses the issue a run worked on.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

# The login the workflow's GITHUB_TOKEN writes as. Only its markers count.
WORKFLOW_BOT_LOGIN = "github-actions[bot]"
# The login the Claude GitHub App writes as: the implementer's and Rework's
# pull requests and replies.
APP_LOGIN = "claude[bot]"

# The branch prefix of an implementer run's work, `agent/issue-<n>`. The
# implementer may be called with another prefix; Rework and Retro read this one,
# and the reusable Rework workflow's head-branch filter names it too.
AGENT_BRANCH_PREFIX = "agent/issue-"

# The caller workflows other runs look up, by file name under .github/workflows/.
WORKFLOWS_DIR = ".github/workflows"
IMPLEMENTER_WORKFLOW = "implementer.yml"
IMPLEMENTER_QUEUE_WORKFLOW = "implementer-queue.yml"
REVIEW_WORKFLOW = "pr-review.yml"
REWORK_WORKFLOW = "rework.yml"
RETRO_WORKFLOW = "retro.yml"
ISSUE_TRIAGE_WORKFLOW = "issue-triage.yml"
SKILL_AUDIT_WORKFLOW = "skill-audit.yml"

# The issue state labels, in vocabulary order. An issue carries at most one.
NEEDS_TRIAGE = "needs-triage"
NEEDS_INFO = "needs-info"
READY_FOR_AGENT = "ready-for-agent"
READY_FOR_HUMAN = "ready-for-human"
WONTFIX = "wontfix"
STATE_LABELS = (NEEDS_TRIAGE, NEEDS_INFO, READY_FOR_AGENT, READY_FOR_HUMAN, WONTFIX)

# Not a state label: it marks an issue an audit run filed as the App, whose body
# counts as a contract once a person adds ready-for-agent (implementer_contract).
AUDIT_FINDING = "audit-finding"

_HEAD = r"[0-9a-f]{40}"
_POSITIVE = r"[1-9][0-9]*"
_FAILURE_HASH = r"[0-9a-f]{16}"
_RUN_NAME = "implementer: issue #{issue}"
_RUN_NAME_PATTERN = re.compile(rf"implementer: issue #(?P<issue>{_POSITIVE})")
# A GitHub expression, as the implementer caller's `run-name` writes the issue.
_EXPRESSION = re.compile(r"\$\{\{.+\}\}")


def workflow_path(file_name: str) -> str:
    """The repository path of a workflow file, as a run's ``path`` carries it."""
    return f"{WORKFLOWS_DIR}/{file_name}"


def state_labels(labels: Sequence[str]) -> list[str]:
    """The state labels among ``labels``, in vocabulary order."""
    return [label for label in STATE_LABELS if label in labels]


def _positive(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _head(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(_HEAD, value) is not None


def _failure_hash(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(_FAILURE_HASH, value) is not None


@dataclass(frozen=True)
class MarkerKind:
    """One marker: its text template, the pattern that reads it, and its field rules."""

    name: str
    template: str
    pattern: re.Pattern[str]
    fields: Mapping[str, Callable[[object], bool]]
    parsers: Mapping[str, Callable[[str], object]]


# `<!-- rework-round:<round> head:<head> -->`: one per Rework run, on the pull request.
REWORK_ROUND = MarkerKind(
    name="rework round",
    template="<!-- rework-round:{round} head:{head} -->",
    pattern=re.compile(rf"<!-- rework-round:(?P<round>{_POSITIVE}) head:(?P<head>{_HEAD}) -->"),
    fields={"round": _positive, "head": _head},
    parsers={"round": int, "head": str},
)
# `<!-- rework-handoff head:<head> -->`: the pull request went to a person for this head.
REWORK_HANDOFF = MarkerKind(
    name="rework handoff",
    template="<!-- rework-handoff head:{head} -->",
    pattern=re.compile(rf"<!-- rework-handoff head:(?P<head>{_HEAD}) -->"),
    fields={"head": _head},
    parsers={"head": str},
)
# `<!-- pr-review-bot -->`: the review's sticky comment, edited in place by `publish`.
REVIEW_STICKY = MarkerKind(
    name="review sticky comment",
    template="<!-- pr-review-bot -->",
    pattern=re.compile(re.escape("<!-- pr-review-bot -->")),
    fields={},
    parsers={},
)
# `<!-- issue-triage-bot -->`: one issue triage comment; their count caps automatic triages.
ISSUE_TRIAGE = MarkerKind(
    name="issue triage comment",
    template="<!-- issue-triage-bot -->",
    pattern=re.compile(re.escape("<!-- issue-triage-bot -->")),
    fields={},
    parsers={},
)
# `<!-- factory-failure:<hash> -->`: the Fix issue for one failure signature.
FIX_ISSUE = MarkerKind(
    name="fix issue",
    template="<!-- factory-failure:{hash} -->",
    pattern=re.compile(rf"<!-- factory-failure:(?P<hash>{_FAILURE_HASH}) -->"),
    fields={"hash": _failure_hash},
    parsers={"hash": str},
)
# `<!-- factory-failure-run:<run id>/<attempt> -->`: one failed run attempt recorded on it.
FIX_RUN = MarkerKind(
    name="fix run record",
    template="<!-- factory-failure-run:{run_id}/{attempt} -->",
    pattern=re.compile(
        rf"<!-- factory-failure-run:(?P<run_id>{_POSITIVE})/(?P<attempt>{_POSITIVE}) -->"
    ),
    fields={"run_id": _positive, "attempt": _positive},
    parsers={"run_id": int, "attempt": int},
)


@dataclass(frozen=True)
class MarkerRead:
    """One bot-authored entry and the fields of each of its markers, in text order."""

    entry: Mapping[str, object]
    markers: tuple[dict[str, object], ...]


def format_marker(kind: MarkerKind, **fields: object) -> str:
    """The marker text for ``fields``; ``ValueError`` when a field breaks the kind's grammar."""
    if set(fields) != set(kind.fields):
        raise ValueError(f"{kind.name} marker takes the fields {sorted(kind.fields)}")
    for name, valid in kind.fields.items():
        if not valid(fields[name]):
            raise ValueError(f"{kind.name} marker field '{name}' is malformed")
    return kind.template.format(**fields)


def read_markers(kind: MarkerKind, entries: Sequence[object]) -> list[MarkerRead]:
    """Each entry by the workflow bot holding a well-formed ``kind`` marker, in entry order.

    An entry is a mapping with ``author`` and ``body``, as
    ``pr_github.comment_entry`` builds it. Entries by anyone else, entries
    without a string body and malformed markers contribute nothing.
    """
    reads: list[MarkerRead] = []
    for entry in entries:
        if not isinstance(entry, Mapping) or entry.get("author") != WORKFLOW_BOT_LOGIN:
            continue
        body = entry.get("body")
        if not isinstance(body, str):
            continue
        markers = tuple(
            {name: kind.parsers[name](match[name]) for name in kind.fields}
            for match in kind.pattern.finditer(body)
        )
        if markers:
            reads.append(MarkerRead(entry, markers))
    return reads


def implementer_run_name(issue: int | str) -> str:
    """The implementer caller's run name for an issue number.

    ``issue`` is a positive number, or the GitHub expression the caller's
    ``run-name`` puts in its place; ``ValueError`` otherwise.
    """
    is_expression = isinstance(issue, str) and _EXPRESSION.fullmatch(issue) is not None
    if not (_positive(issue) or is_expression):
        raise ValueError("implementer run name takes a positive issue number")
    return _RUN_NAME.format(issue=issue)


def implementer_run_issue(title: object) -> int | None:
    """The issue number an implementer run title names; ``None`` for any other title."""
    if not isinstance(title, str):
        return None
    found = _RUN_NAME_PATTERN.fullmatch(title)
    return int(found["issue"]) if found else None


def agent_branch(issue: int, prefix: str = AGENT_BRANCH_PREFIX) -> str:
    """The branch an implementer run works on for an issue number."""
    return f"{prefix}{issue}"


def agent_branch_issue(ref: object, prefix: str = AGENT_BRANCH_PREFIX) -> int | None:
    """The issue number the whole ref ``prefix<n>`` names; ``None`` for any other ref."""
    if not isinstance(ref, str) or not ref.startswith(prefix):
        return None
    found = re.fullmatch(_POSITIVE, ref[len(prefix) :])
    return int(found[0]) if found else None
