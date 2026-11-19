# Subagents start with ~92k tokens of unused tools

- 2026-11-19 retro of two chief-of-staff subagents (a browser audit of four
  tools, and the smoke-suite build for `fabiandistler/tools`): each started at
  about 92k tokens of tool and connector definitions it never called, 45–57 % of
  its total tokens. The four parallel audits used 286k–312k tokens each.
- Proposed fix (2026-11-19, not built): a tool-restricted agent definition for
  browser audits (Read, Grep, Glob, Bash, Write) in the agents plugins, so
  fan-out work stops paying for unused schemas. Unverified: how much of the
  92k a `tools:` restriction actually removes.
- Why it matters: subagents share one 5-hour budget with the implementer
  ([shared usage limit](shared-usage-limit.md)).
