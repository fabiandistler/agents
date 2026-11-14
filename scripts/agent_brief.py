"""Which comment on an issue is its Agent Brief.

Anyone can write on a public issue. Only the repository's owner, members and
collaborators can write the brief: the latest of their comments that contains a
`## Agent Brief` heading. The implementer works to that brief
(``implementer_contract.py``), and the PR review checks an agent's pull request
against the same text (``pr_github.py --linked-issues``).

The heading may stand at the start of any line of the comment's prose, because
a triage comment opens with the AI disclaimer before it. Trust is decided by the
comment's author alone, so a trusted comment that holds the brief in a
`<details>` block counts too. The triage bot's draft brief does not: the bot
posts as `github-actions[bot]`, whose association is not a trusted one, and the
draft is the maintainer's to post (ADR-0013).

Standard library only.
"""

from __future__ import annotations

import re

from check_pr_issue_links import markdown_prose
from issue_triage_policy import TRUSTED_ASSOCIATIONS

# Code blocks, inline code and HTML comments hold no heading: markdown_prose drops them.
AGENT_BRIEF_HEADING = re.compile(r"^ {0,3}## Agent Brief\b", re.MULTILINE)


def is_trusted(item: dict) -> bool:
    """Whether an issue or comment's author has write access; a missing association does not."""
    return item.get("author_association") in TRUSTED_ASSOCIATIONS


def is_agent_brief(text: str) -> bool:
    """Whether a comment's prose has a `## Agent Brief` heading at the start of a line."""
    return AGENT_BRIEF_HEADING.search(markdown_prose(text)) is not None
