# PR review comments

For an operator of the review scripts. A review round that cannot see the
answers to the last one reports the same findings again, so `pr_review.py`
passes the pull request's comments by people with write access to the model.
The jobs and the security model are in the [runbook](pr-review-runbook.md).

- **Which comments.** `pr_github.py` always fetches the pull request's issue
  comments into the context field `comments`, each
  `{"id", "body": str, "author": str, "author_association": str}`. The
  review keeps those whose `author_association` is `OWNER`, `MEMBER` or
  `COLLABORATOR` (`is_trusted` in `scripts/agent_brief.py`, the rule the
  implementer's contract uses). A missing association counts as untrusted.
  The review bot's own sticky comment (`is_sticky_comment` in
  `scripts/pr_comment.py`) is left out; a human comment quoting its marker is
  kept. Review comments on diff lines are not read.
- **In the payload.** A `PULL REQUEST COMMENTS (...)` section after the linked
  issues, oldest first, each comment between `=== comment by <login> ===` and
  `=== end comment ===`. Each is sanitized like the pull request text and
  capped at 10,000 bytes. The section takes the room the payload leaves; newer
  comments win it, and a line counts the dropped older ones. Comment text never
  marks the review partial and never enters the system prompt.
- **Still untrusted.** The prompt names the comments as untrusted data. A
  rebuttal is evidence the model weighs against the diff and the base files,
  not an instruction; it repeats an answered finding only when the input shows
  the answer is wrong.
- **Malformed field.** `pr_review.py` rejects a `comments` field that is not a
  list of objects with a string `body` and `author` with exit 3.
