---
name: handoff
environments: coding
description: Compact the current conversation into a handoff document for another agent to pick up.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
---

Write a handoff document summarising the current conversation so a fresh agent can continue the work. Save to the temporary directory of the user's OS - not the current workspace, to avoid polluting it. As the final step, state the absolute path of the written file so the user can pass it to the next session.

Cover at minimum: the goal, the current state, what is done and what remains, key decisions with their rationale, open questions or blockers, how to resume (entry points, commands), and relevant files or artifacts by path.

Include a "suggested skills" section in the document, which suggests skills that the agent should invoke.

Do not duplicate content already captured in other artifacts (PRDs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

If the user passed arguments, treat them as a description of what the next session will focus on and tailor the doc accordingly.
