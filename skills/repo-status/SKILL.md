---
name: repo-status
category: workflow
activation: command
disable-model-invocation: true
environments: coding, chat
argument-hint: "[yesterday | today | blockers | <topic>]"
description: Generate a standup / status update from recent development activity — yesterday/today/blockers, turning rough notes or connected-tool activity into a shareable update.
---

# Repo Status

Turn recent activity into a short async standup update for a team channel.
Draft first; ask afterwards.

## When to use

This skill covers the short, team-facing update: a small window, an optional
goal line plus yesterday/today/blockers, no clarifying round before the draft.

For a periodic or event-driven update aimed outside the working group — a weekly
or monthly status to leadership, a launch announcement, a risk escalation, or the
same progress retold for partners or customers — use the `stakeholder-update`
skill instead, which settles audience and update type before drafting.

## Get the raw material

**Pull it from connected tools** instead of asking the user to recall it:

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
The user can override the window — name the actual window under the header so
the reader knows what "Yesterday" covers.

### In a repository

When working inside a git checkout, prefer these commands over recall. Keep
two identities apart:

- Commit identity, for `git log --author`: the user's stated commit email or
  name. `--author` matches commit name/email, so a GitHub login there usually
  matches nothing. If neither is known, run without `--author`, say in the
  report that commits are unfiltered, and ask for it afterwards. Never take it from
  `git config user.email`: the local git identity can differ from the user's,
  e.g. in a cloud or shared checkout.
- GitHub identity, for `gh`: `@me`.

Then:

- Commits: `git log --all --no-merges --since=<window> --author=<commit-email-or-name>`
- PRs authored: `gh search prs --author=@me --updated=">=<date>" --json number,title,state,repository`
- PRs reviewed: `gh search prs --reviewed-by=@me --updated=">=<date>" --json number,title,state,repository`
- CI status: `gh run list --limit 5`

Without `gh`, fall back to git-only and structure what the user tells you.

**Or structure what the user tells you.** If nothing is connected, or the user just narrates, organize those notes into the format below.

## Output format

Produce this structure:

```markdown
## Standup — [<date>]

**Focus:** [one-line goal this update serves — omit when there is none]
**Window:** [<start date> → <end date>]

### Yesterday
- [Outcome reached, with a ticket/PR reference where there is one]

### Today
- [Outcome aimed for, with a ticket reference where there is one]

### Blockers
- [What is stuck, who can unblock it, and what is needed from them]
```

Write outcomes, not activity: the result ("auth migration live behind its flag")
rather than the motion ("worked on auth"). Each blocker names who can unblock
it and what is needed. With no blockers, write "None".

### Scoping with the argument

With `yesterday`, `today`, or `blockers`, produce only that section. With
free-text scope, filter all three sections to that topic. With no argument,
produce all three.

## Formatting for where it's going

If the user names a destination, match its conventions; otherwise the Markdown above is a safe default.
