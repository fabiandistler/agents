# Subagents start with ~92k tokens of unused tools

- 2026-11-19 retro of two chief-of-staff subagents (a browser audit of four
  tools, and the smoke-suite build for `fabiandistler/tools`): each started at
  about 92k tokens of tool and connector definitions it never called, 45–57 % of
  its total tokens. The four parallel audits used 286k–312k tokens each.
- Proposed fix (2026-11-19, not built): a tool-restricted agent definition for
  browser audits (Read, Grep, Glob, Bash, Write) in the agents plugins, so
  fan-out work stops paying for unused schemas. Unverified: how much of the
  92k a `tools:` restriction actually removes.
- 2026-11-19: agents#903 adds `plugins/workflow/agents/browser-worker.md` with
  tools Read, Grep, Glob, Bash, Edit, Write and three GitHub MCP tools. Docs
  (code.claude.com/docs/en/sub-agents, "restrict which tools a subagent can
  use") say an agent whose `tools:` list names no MCP tool can use none.
  Unmeasured: whether MCP server instructions and the skill listing also drop.
  Measure the first browser-worker run's starting context against the 81.5k a
  general-purpose subagent started with (figure from the agents#903 run). The PR
  also changes the OpenCode installer, which rejected `mcp__` tool names.
- Why it matters: subagents share one 5-hour budget with the implementer
  ([shared usage limit](shared-usage-limit.md)).
