# Subagents start with ~92k tokens of unused tools

- 2026-11-19 retro of two chief-of-staff subagents (a browser audit of four
  tools, and the smoke-suite build for `fabiandistler/tools`): each started at
  about 92k tokens of tool and connector definitions it never called, 45–57 % of
  its total tokens. The four parallel audits used 286k–312k tokens each.
- Proposed fix (2026-11-19, not built): a tool-restricted agent definition for
  browser audits (Read, Grep, Glob, Bash, Write) in the agents plugins, so
  fan-out work stops paying for unused schemas. Unverified: how much of the
  92k a `tools:` restriction actually removes. *Superseded 2026-11-20, see
  below.*
- 2026-11-19: agents#903 adds `plugins/workflow/agents/browser-worker.md` with
  tools Read, Grep, Glob, Bash, Edit, Write and three GitHub MCP tools. Docs
  (code.claude.com/docs/en/sub-agents, "restrict which tools a subagent can
  use") say an agent whose `tools:` list names no MCP tool can use none.
  Unmeasured: whether MCP server instructions and the skill listing also drop.
  Measure the first browser-worker run's starting context against the 81.5k a
  general-purpose subagent started with (figure from the agents#903 run).
  *Superseded 2026-11-20, see below.* The PR
  also changes the OpenCode installer, which rejected `mcp__` tool names.
- 2026-11-20: three chief-of-staff subagents used the browser-worker type:
  the first wiki ingest (PR #906), #908 and #910. Their reported totals were
  186k, 119k and 168k tokens. General-purpose subagents the same day
  reported 119k–467k. This is not a like-for-like comparison: the tasks
  differed in kind and size. The starting context of a browser-worker run is
  still unmeasured, so the 2026-11-19 question stays open. *Superseded
  2026-11-20, see below.*
- 2026-11-20 (supersedes the "unverified" and "unmeasured" notes above):
  the chief-of-staff retro of that day read the starting context from each
  API response's `usage`. The first wiki ingest (PR #906, browser-worker)
  started at ~14.0k tokens; two general-purpose subagents the same day (the
  maintenance cadence and the maintenance-on-Actions spec) started at 82.5k
  and 83.4k. So the `tools:` restriction removed about 68.5k tokens (83 %)
  of starting context. Carried over their API turns, that load was 2.6M of
  12.2M (21 %) and 4.3M of 15.0M (29 %) input tokens of the two
  general-purpose runs. The 14.0k bounds whatever stayed (the allowed tools,
  any server instructions, the skill listing); the split was not measured,
  nor whether naming a Firecrawl or claude-code-remote tool in `tools:`
  brings back its server's instructions.
- Why it matters: subagents share one 5-hour budget with the implementer
  ([shared usage limit](shared-usage-limit.md)).
