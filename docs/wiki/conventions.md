# Wiki conventions

Decided 2026-10-19 (see [wiki location](decisions/2026-10-19-wiki-location.md)).

- One page per thing: a decision, a recurring problem, a subsystem, a preference.
- Date every claim. Claims about code cite `fabiandistler/agents@<sha>`.
- Never "currently"/"is" about code without a date or commit.
- On change, append a new dated claim and mark the old one *superseded*; do not rewrite it.
- Sources (issues, PRs, subagent reports) are cited, never copied.
- Every page is listed in [index](index.md).

## Briefs

Added 2026-11-20 from the chief-of-staff retro of that day: rules for the subagent briefs that chief-of-staff sessions write. They live here because a re-run of `scripts/vendor_mattpocock_skills.py` replaces the vendored `.claude/skills/chief-of-staff/` (`INCLUDED_IN_PROGRESS`, lines 64-67, and the copy at lines 139-141, `fabiandistler/agents@94e1b19`); the skill follows a shared wiki's own conventions (`.claude/skills/chief-of-staff/SKILL.md:28`).

- A wiki PR stays at ≤300 changed lines so bot auto-merge can arm: above that `scripts/pr_risk.py:246-248` rates it risk:medium (`fabiandistler/agents@94e1b19`), and #906 (730 lines) needed a manual merge.
- Pass scheduled-task ids and use `get_trigger`, never `list_triggers`: it returns all 34 stored prompts, +101k tokens on 2026-11-20 ([listing-tool cost](problems/listing-tool-cost.md)).
- GitHub search queries carry `is:issue` or `is:pr`: without one, `gh api search/issues` returns HTTP 422 (reproduced 2026-11-20).
- Prefer one `gh api search/issues` query over paging list tools: 8 `list_pull_requests` pages added 120k tokens where one search returned 873 characters ([listing-tool cost](problems/listing-tool-cost.md)).
- Read-only sweeps use a tool-restricted agent type: on 2026-11-20 a browser-worker subagent started at 14k tokens, two general-purpose ones at 82–83k.
- Verify a claim before telling the maintainer it is obsolete: ADR-0014's reason was called probably obsolete and held ([2026-11-20 decisions](decisions/2026-11-20-decisions.md)).
