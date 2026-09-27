---
name: repo-status
category: workflow
activation: command
disable-model-invocation: true
environments: coding, chat
argument-hint: "[yesterday | today | blockers]"
description: Generate a standup / status update from recent development activity — yesterday/today/blockers, turning rough notes or connected-tool activity into a shareable update.
---

# Repo Status

Turn recent development activity into a short, shareable async standup update —
the kind people paste into a team channel instead of reading out at a meeting.
Bias toward producing a usable draft quickly rather than interrogating the user
for details. Draft first; ask afterwards.

## When to use

This skill covers the short, team-facing update: a small window, an optional
goal line plus yesterday/today/blockers, no clarifying round before the draft.

For a periodic or event-driven update aimed outside the working group — a weekly
or monthly status to leadership, a launch announcement, a risk escalation, or the
same progress retold for partners or customers — use the `stakeholder-update`
skill instead, which settles audience and update type before drafting.

## Get the raw material

There are two ways to gather what happened; prefer the first.

**Pull it from connected tools.** If the user has development tools connected,
gather the activity yourself instead of asking them to recall it:

- **Source control** — commits, and pull requests opened, reviewed, or merged in
  the window. Summarize the *change*, not the commit text.
- **Issue / project tracker** — tickets that moved and what is queued next.
  Carry the ticket reference into the output so teammates can click through.
- **Team chat** — decisions reached in shared channels and threads waiting on
  the user. Surface only items the update's audience may see: shared channels,
  never direct messages or other private conversations. When unsure whether an
  item is shareable, leave it out or ask the user before including it.
- **CI / CD** — recent build or deploy status, especially anything red.

Use whatever subset is actually connected; don't block on tools that aren't
there.

### Reporting window

Default to the last working day's start → now (on Monday, start Friday 00:00).
The user can override the window — put the actual window in the header so the
reader knows what "Yesterday" covers.

### In a repository

When working inside a git checkout, prefer these commands over recall. Resolve
the author with `gh api user --jq .login` or the user's stated email — never
`git config user.email`.

- Commits: `git log --all --no-merges --since=<window> --author=<id>`
- PRs authored: `gh search prs --author=@me --updated=">=<date>" --json number,title,state,repository`
- PRs reviewed: `gh search prs --reviewed-by=@me --updated=">=<date>" --json number,title,state,repository`
- CI status: `gh run list --limit 5`

If `gh` is missing or unauthenticated, fall back to git-only and structure
what the user tells you for PRs and CI.

**Or structure what the user tells you.** If nothing is connected, or the user just narrates, organize those notes into the format below.

## Output format

Produce this structure:

```markdown
## Repo Status — [<start date> → <end date>]

**Focus:** [one-line goal this update serves — omit when there is none]

### Yesterday
- [Outcome reached, with a ticket/PR reference where there is one]

### Today
- [Outcome aimed for, with a ticket reference where there is one]

### Blockers
- [What is stuck, who can unblock it, and what is needed from them]
```

Write outcomes, not activity: the result ("auth migration live behind its flag")
rather than the motion ("worked on auth"). Each blocker names who can unblock
it and what is needed from them. With no blockers, write "None" below the heading.

### Scoping with the argument

With `yesterday`, `today`, or `blockers`, produce only that section. With no
argument, produce all three.

## Formatting for where it's going

If the user names a destination, match its conventions; otherwise the Markdown above is a safe default.
