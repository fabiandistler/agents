"""The state rules of the automated issue triage, free of I/O.

Two decisions live here, both pure functions over issue data:

- ``assess`` decides whether a trigger may start a model run on an issue: who
  wrote it, which state label it carries, and how many automated triages it
  has already had.
- ``plan_labels`` turns the model's recommended state into label changes. The
  bot sets ``needs-info`` itself and nothing else: every other recommendation
  leaves the issue in ``needs-triage`` for the maintainer, who applies the
  state (docs/agents/triage-labels.md, ADR-0013).

The state label strings follow docs/agents/triage-labels.md;
scripts/test_issue_triage_policy.py keeps them in sync with that table.
"""

from __future__ import annotations

from datetime import datetime

NEEDS_TRIAGE = "needs-triage"
NEEDS_INFO = "needs-info"
READY_FOR_AGENT = "ready-for-agent"
READY_FOR_HUMAN = "ready-for-human"
WONTFIX = "wontfix"
STATE_LABELS = (NEEDS_TRIAGE, NEEDS_INFO, READY_FOR_AGENT, READY_FOR_HUMAN, WONTFIX)
# What the model may recommend: every state except the one it starts from.
RECOMMENDABLE_STATES = (NEEDS_INFO, READY_FOR_AGENT, READY_FOR_HUMAN, WONTFIX)
# The only state the bot applies on its own.
BOT_STATES = (NEEDS_INFO,)
CATEGORIES = ("bug", "enhancement")

# The triage comment is found by this marker and its author, the workflow bot.
COMMENT_MARKER = "<!-- issue-triage-bot -->"
COMMENT_AUTHOR = "github-actions[bot]"

# Only issues by people with write access reach the model: the repository is
# public, and both the subscription quota and the prompt are theirs to spend.
TRUSTED_ASSOCIATIONS = ("OWNER", "MEMBER", "COLLABORATOR")

# Triggers. `opened` and `reply` are automatic and capped; `relabel` (the
# maintainer adds needs-triage) and `dispatch` (a manual run) come from a
# human and are not.
TRIGGERS = ("opened", "reply", "relabel", "dispatch")
AUTOMATIC_TRIGGERS = ("opened", "reply")
# Automated triages per issue: the first on open, one more after the
# reporter answers needs-info. After that only the maintainer re-triggers.
MAX_AUTOMATIC_TRIAGES = 2


def state_labels(labels: list[str]) -> list[str]:
    """The state labels among ``labels``, in vocabulary order."""
    return [label for label in STATE_LABELS if label in labels]


def _is_bot_triage(comment: dict) -> bool:
    return comment.get("author") == COMMENT_AUTHOR and COMMENT_MARKER in (comment.get("body") or "")


def count_bot_triages(comments: list[dict]) -> int:
    """Count the triage comments the workflow bot posted on the issue."""
    return sum(1 for comment in comments if _is_bot_triage(comment))


def parse_time(text: str) -> datetime:
    """An ISO 8601 time with a UTC offset, as GitHub sends ``created_at``.

    Raises ValueError for any other text, and for a time without an offset,
    which cannot be compared with one that has it.
    """
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        raise ValueError("the time has no UTC offset")
    return moment


def _relabeled_since_last_triage(comments: list[dict], label_events: list[dict]) -> bool:
    """Whether a person added needs-triage after the newest bot triage.

    Creating an issue with needs-triage yields a ``labeled`` event older than
    the triage it led to, and a bot's ``labeled`` event (the reply requeue)
    never counts: only a maintainer's later re-add asks for another run.
    """
    newest_triage = max(
        parse_time(comment["created_at"]) for comment in comments if _is_bot_triage(comment)
    )
    return any(
        parse_time(event["created_at"]) > newest_triage
        for event in label_events
        if event["label"] == NEEDS_TRIAGE and event["actor_type"] != "Bot"
    )


def _expected_states(trigger: str) -> tuple[frozenset[str], ...]:
    """The state-label sets a trigger may start from."""
    if trigger == "reply":
        return (frozenset({NEEDS_INFO}),)
    # A new issue may not carry needs-triage yet: triage-label.yml adds it in
    # a parallel run.
    return (frozenset(), frozenset({NEEDS_TRIAGE}))


def assess(issue: dict, comments: list[dict], trigger: str) -> dict:
    """Decide whether ``trigger`` may start a triage run on ``issue``.

    ``issue`` carries ``state``, ``is_pull_request``, ``author_type``,
    ``author_association``, ``labels`` and ``label_events``: the issue's
    ``labeled`` events, each with ``label``, ``actor_type`` and ``created_at``
    (ISO 8601). Each comment carries ``author``, ``body`` and ``created_at``.
    An ``opened`` run is only ever the first triage; a ``relabel`` run after a
    bot triage needs a person's newer needs-triage label event.

    Returns ``eligible``, the ``skip_reason`` when it is not, the current
    ``states`` labels, the number of earlier automated triages, and
    ``requeue``: whether a reply moves the issue back to needs-triage even
    without a usable triage.
    """
    if trigger not in TRIGGERS:
        raise ValueError(f"trigger must be one of {TRIGGERS}")
    states = state_labels(issue["labels"])
    bot_triages = count_bot_triages(comments)
    decision = {"eligible": False, "skip_reason": None, "states": states}
    decision["bot_triages"] = bot_triages
    # The reporter answered needs-info: the issue goes back to needs-triage
    # whether or not a model run follows (limit reached, outside author, failed
    # call). That move needs no model, so it is decided here on its own.
    decision["requeue"] = (
        trigger == "reply"
        and issue["state"] == "open"
        and not issue["is_pull_request"]
        and states == [NEEDS_INFO]
    )
    if issue["is_pull_request"]:
        decision["skip_reason"] = "pull requests are not triaged"
    elif issue["state"] != "open":
        decision["skip_reason"] = "the issue is closed"
    elif issue["author_type"] == "Bot":
        decision["skip_reason"] = "the issue was opened by a bot"
    elif issue["author_association"] not in TRUSTED_ASSOCIATIONS:
        decision["skip_reason"] = "the author has no write access to the repository"
    elif len(states) > 1:
        decision["skip_reason"] = "the issue carries conflicting state labels"
    elif frozenset(states) not in _expected_states(trigger):
        decision["skip_reason"] = "the issue is not waiting for triage"
    elif trigger == "opened" and bot_triages > 0:
        decision["skip_reason"] = "the issue already had its first triage"
    elif (
        trigger == "relabel"
        and bot_triages > 0
        and not _relabeled_since_last_triage(comments, issue["label_events"])
    ):
        decision["skip_reason"] = "no person added needs-triage since the last triage"
    elif trigger in AUTOMATIC_TRIGGERS and bot_triages >= MAX_AUTOMATIC_TRIAGES:
        decision["skip_reason"] = "the automated triage limit is reached"
    else:
        decision["eligible"] = True
    return decision


def unchanged_since_assessment(assessed: list[str], current: list[str]) -> bool:
    """Whether the state labels still are what the assessment saw.

    triage-label.yml adds needs-triage to a new issue in a parallel run, so an
    issue assessed without a state that now carries needs-triage is unchanged.
    """
    now = state_labels(current)
    return now == assessed or (not assessed and now == [NEEDS_TRIAGE])


def target_state(recommended: str) -> str:
    """The state label the bot leaves on the issue for a recommendation."""
    return recommended if recommended in BOT_STATES else NEEDS_TRIAGE


def plan_labels(current_labels: list[str], recommended: str) -> dict:
    """The label changes that bring the issue to ``target_state(recommended)``.

    Returns ``add`` and ``remove`` lists; both are empty when the issue already
    carries exactly the target state.
    """
    target = target_state(recommended)
    states = state_labels(current_labels)
    return {
        "add": [] if target in states else [target],
        "remove": [label for label in states if label != target],
    }
