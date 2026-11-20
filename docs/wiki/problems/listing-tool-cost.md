# Listing tools cost more than the lookups they replace

Source: the chief-of-staff retro of 2026-11-20, which read the transcript of
that morning's maintenance-cadence subagent (general-purpose, 38 API turns,
12.2M input tokens). Token figures come from each API response's `usage`;
"carried" means context growth times the API turns that re-read it.

- 2026-11-20: the brief prescribed `list_triggers`. Four pages (12, 9, 7 and
  6 entries) covered all 34 scheduled tasks: 161k characters, +101k context
  tokens, about 3.4M carried (28 % of the run), so about 3k tokens per
  trigger. Each entry carries its stored prompt (`derived_state.prompt`,
  median entry 4.5k characters). The tool has no name or field filter, and
  `recurring: true` would still return 30 of the 34. The run needed 3.
- 2026-11-20: the brief prescribed `list_pull_requests`. 8 calls (agents
  pages 1–6, repo-maintenance, dotfiles) returned 294k characters, +120k
  context tokens, about 3.0M carried (25 %): about 20k tokens per page of 100
  PRs. They fetched about 665 PRs to find 35 maintenance PRs; the tool has no
  branch-prefix filter.
- 2026-11-20, the cheaper calls:
  - `get_trigger` with the ids in [schedules](../schedules.md), which names
    the three maintenance routines as of `fabiandistler/agents@18fb575`.
  - One search per repository:
    `gh api -X GET search/issues -f q='repo:fabiandistler/agents is:pr head:maintenance/' --jq '[.items[]|{number,state,merged_at:.pull_request.merged_at}]'`
    returned all 13 agents maintenance PRs in 873 characters; the same query
    found 14 in repo-maintenance and 8 in dotfiles. `head:` matches a
    branch-name prefix. The query needs `is:issue` or `is:pr`, or the API
    answers HTTP 422 (reproduced 2026-11-20). In these cloud sessions
    `gh auth status` reports the token as invalid, yet `gh api` REST works,
    and the GitHub MCP exposes no `search_*` tool.
- 2026-11-20: planned, not built: an `analyst` subagent type, a read-only,
  tool-restricted worker for evidence gathering, analyses and spec drafts,
  so such briefs stop starting with the general-purpose tool load. PR
  pending.

Related: [briefs](../conventions.md#briefs),
[subagent tool overhead](subagent-tool-overhead.md),
[shared usage limit](shared-usage-limit.md).
