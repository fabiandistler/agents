---
name: repo-status
category: workflow
environments: coding
description: Generate a status update from recent activity. Use when preparing for daily standup, summarizing yesterday's commits and PRs and ticket moves, formatting work into yesterday/today/blockers, or structuring a few rough notes into a shareable update.
argument-hint: "[yesterday | today | blockers]"
---

# Repo Status

Generate a status update by pulling together recent activity across your tools.

## What I Need From You

**Option A: Let me pull it**
If your tools are connected, ask for a repo status and I'll gather everything automatically.

**Option B: Tell me what you did**
"Worked on the auth migration, reviewed 3 PRs, got blocked on the API rate limiting issue."

## Output

```markdown
## Repo Status — [Date]

### Yesterday
- [Completed item with ticket reference if available]
- [Completed item]

### Today
- [Planned item with ticket reference]
- [Planned item]

### Blockers
- [Blocker with context and who can help]
```

## If Connectors Available

If **source control** is connected:
- Pull recent commits and PRs (opened, reviewed, merged)
- Summarize code changes at a high level

If a **project tracker** is connected:
- Pull tickets moved to "in progress" or "done"
- Show upcoming sprint items

If **chat** is connected:
- Scan for relevant discussions and decisions
- Flag threads needing your response

If **CI/CD** is connected:
- Pull recent build and deploy status

## Tips

1. **Run it every morning** — Build a habit and never scramble for standup notes.
2. **Add context** — After I generate, add any nuance about blockers or priorities.
3. **Share format** — Ask me to format for Slack, email, or your team's standup tool.
