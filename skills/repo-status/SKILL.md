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

Turn recent development activity into a short, shareable status update — the kind
people read out at a daily standup or paste into a team channel. The value is
saving the user from reconstructing "what did I actually do yesterday" under time
pressure, so bias toward producing a usable draft quickly rather than
interrogating them for details. Draft first; ask afterwards.

## When to use

This skill covers the daily, team-facing update: a short window of activity, a
fixed three-part shape, and no clarifying round before the first draft.

For a periodic or event-driven update aimed outside the working group — a weekly
or monthly status to leadership, a launch announcement, a risk escalation, or the
same progress retold for partners or customers — use the `stakeholder-update`
skill instead, which settles audience and update type before drafting.

## Get the raw material

There are two ways to gather what happened. Prefer the first; fall back to the
second.

**Pull it from connected tools.** If the user has development tools connected,
gather the activity yourself instead of asking them to recall it — reconstructing
a day from memory is exactly the chore this skill removes. What to look for, by
kind of tool:

- **Source control** — commits, and pull requests opened, reviewed, or merged in
  the window. Summarize the *change*, not the commit text ("finished the auth
  migration", not "fix typo in auth.py"). Note the repo or branch if several are
  in play.
- **Issue / project tracker** — tickets that moved (to in-progress, to done) and
  what's queued for the sprint. Carry the ticket reference into the output so
  teammates can click through — an item without its reference is harder to act on.
- **Team chat** — decisions reached and threads that are waiting on the user.
  A thread awaiting their reply is often a real blocker in disguise.
- **CI / CD** — recent build or deploy status, especially anything red, since a
  broken pipeline is usually the most time-sensitive line in a standup.

Use whatever subset is actually connected; don't block on tools that aren't
there. Stay tool-agnostic in how you describe this to the user — talk about
"your source control" or "your tracker", not a specific product.

**Or structure what the user tells you.** If nothing is connected, or the user
just narrates ("worked on the auth migration, reviewed a couple PRs, stuck on the
API rate limiting"), take those notes and organize them into the format below.
Ask a brief follow-up only when a blocker's owner or a ticket reference is
missing and would clearly make the update more useful — otherwise draft first and
let them refine.

## Output format

Produce this structure. It maps directly onto how standups are run —
yesterday's progress, today's plan, what's in the way — so it's instantly
familiar to whoever reads it:

```markdown
## Repo Status — [Date]

### Yesterday
- [What got done, with a ticket/PR reference where there is one]

### Today
- [What's planned, with a ticket reference where there is one]

### Blockers
- [What's stuck, with context and who can unblock it]
```

If there are genuinely no blockers, keep the heading and write "None" under it
rather than dropping the section — an explicit "no blockers" is a signal
teammates rely on.

### Scoping with the argument

If the user passed `yesterday`, `today`, or `blockers`, produce only that
section — they want one slice, not the whole update (e.g. someone asks just
"what am I blocked on?" mid-morning). With no argument, produce all three.

## Formatting for where it's going

A standup update usually gets pasted somewhere. If the user names a
destination — Slack, email, their team's standup tool — match its conventions
(tighter plain-text bullets for a chat channel, a short greeting and sign-off for
email). If they don't say, the Markdown above is a safe default; ask only if the
destination clearly changes the formatting.
