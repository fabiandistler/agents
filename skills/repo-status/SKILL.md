---
name: repo-status
category: workflow
activation: command
disable-model-invocation: true
environments: coding, chat
argument-hint: "[yesterday | today | blockers | <topic>]"
description: Generates a standup or status update from recent development activity, including yesterday's work, today's plan, and blockers, using rough notes or connected-tool activity.
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
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
- GitHub identity, for PR search: `@me`, or the authenticated user's login
  (`gh api user --jq .login`, or the GitHub MCP `get_me`).

Then:

- Commits: `git log --all --no-merges --since=<window> --author=<commit-email-or-name>`
- PRs authored and PRs reviewed since `<date>`: search pull requests by author
  and by reviewer. Use the GitHub MCP tools if the session has them; otherwise
  `gh search prs --author=@me --updated=">=<date>" --json number,title,state,repository`
  and the same with `--reviewed-by=@me`. Where search is refused (sessions
  bound to their configured repositories reject `search/*`), list each
  repo's PRs instead (the repos from `git remote -v`, or the ones the user
  names) with the GitHub MCP tools or the loop below,
  keeping those whose login column is yours. It pages by hand and stops at
  the first page that is not entirely inside the window: the list is sorted
  by `updated_at`, so later pages are older. Do not use `gh api --paginate`
  here: it walks the repo's whole PR history, and it follows `Link` URLs of
  the form `repositories/<id>/…`, which some proxies refuse with HTTP 403.

  ```bash
  page=1
  while :; do
    prs=$(gh api "repos/<owner>/<repo>/pulls?state=all&sort=updated&direction=desc&per_page=100&page=$page" \
      --jq '.[] | select(.updated_at >= "<date>") | [.number, .user.login, .state, .title] | @tsv') || break
    [ -n "$prs" ] && printf '%s\n' "$prs"
    [ "$(printf '%s' "$prs" | grep -c .)" -eq 100 ] || break
    page=$((page + 1))
  done
  ```

  For reviewed PRs, page through every review and keep the login/date filter
  on the rows. The first output value is the raw page size, so a full page
  continues even when none of its reviews match:

  ```bash
  page=1
  while :; do
    review_page=$(gh api "repos/<owner>/<repo>/pulls/<n>/reviews?per_page=100&page=$page" \
      --jq '[length] + [.[] | select(.user.login == "<login>" and .submitted_at >= "<date>") | .state] | .[]') || break
    review_count=${review_page%%$'\n'*}
    review_states=$(printf '%s\n' "$review_page" | tail -n +2)
    [ -n "$review_states" ] && printf '%s\n' "$review_states"
    [ "$review_count" -eq 100 ] || break
    page=$((page + 1))
  done
  ```
- CI status: `gh run list --limit 5`

Without the GitHub MCP tools or `gh`, fall back to git-only and structure what
the user tells you.

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
