# PR review linked issues

For an operator of the review scripts. `pr_github.py --linked-issues` adds the
issues a pull request says it closes to the context, so the model can check
the diff against the ticket. Without the flag the context, the request and the
risk are unchanged. The jobs and the security model are in the
[runbook](pr-review-runbook.md).

- **Which issues.** The closing references in the pull request body
  (`Closes #n`, parsed by `closing_references` in
  `scripts/check_pr_issue_links.py`), same repository only, deduplicated,
  ascending, at most 3. Each is one REST `GET /repos/{owner}/{repo}/issues/{n}`
  with the job's token. Native sidebar links (GraphQL only), issue comments
  and other repositories' issues are not read. A reference that turns out to
  be a pull request is dropped.
- **The field.** `linked_issues` is a list of
  `{"number": int, "status": "ok" | "unavailable" | "outside_author",
  "title": str, "body": str}`; a pull request without a closing reference gets
  `[]`. The field is additive, so `schema_version` stays 1. `pr_review.py`
  rejects a malformed field with exit 3; `pr_risk.py` ignores it.
- **Trusted authors only.** Title and body are kept only when the issue's
  `author_association` is `OWNER`, `MEMBER` or `COLLABORATOR`
  (`TRUSTED_ASSOCIATIONS`, as for issue triage, ADR-0013). Any other issue is
  `outside_author` with empty text and is rendered as
  `(issue #n is not shown: outside author)`.
- **A failed fetch is not a failed run.** A 404, 403, 5xx or invalid JSON
  makes that issue `unavailable`, rendered as `(issue #n could not be
  fetched)`, with one stderr line naming the issue number and HTTP status,
  never its text. No retry; the context fetch still exits 0.
- **In the payload.** A `LINKED ISSUES (untrusted: ...)` section after
  `=== END OF DIFF ===`, each issue between `=== issue #n ===` and
  `=== end issue #n ===`. Title and body are sanitized like the pull request
  text; the title is capped at 500 bytes, the body at 20,000 bytes. The
  section is rendered last, into the room the capped payload leaves, and a cut
  adds `(issue text truncated)`. Issue text never marks the review partial and
  never displaces a diff line. It never enters the system prompt.

```bash
python3 "$scripts/pr_github.py" --repo fabiandistler/agents --pr "$pr" \
  --linked-issues --output context.json
```
