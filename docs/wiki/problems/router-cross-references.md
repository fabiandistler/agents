# Router cross-references

- 2026-10-19: Per the backlog survey, 7 of the 8 open errors in the rolling
  skill-audit issue (#466) share one cause: architecture skills (and one
  ai-ml skill) refer to sibling router members as if they were standalone,
  invocable skills. AGENTS.md's "Cross-skill references" convention forbids
  this, but as of `fabiandistler/agents@a9b3494` no CI check enforces it.
- Same mistake class: stale references left after removing the prek-hooks
  and adr-workflow skills (see merged PR history in #466).
- Open choice (2026-10-19): rewrite references to the router form, or
  amend the convention. Either way, add a cross-reference check to CI.

Related: [unrunnable commands](unrunnable-skill-commands.md).
- 2026-10-19: Resolved in favour of rewriting, see
  [decision](../decisions/2026-10-19-router-references.md).
