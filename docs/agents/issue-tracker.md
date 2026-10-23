# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. For every operation below, use the GitHub MCP tools if the session has them; otherwise `gh` with the command given. GraphQL-backed `gh` porcelain (`gh issue`, `gh pr`) fails in sessions where GitHub's GraphQL endpoint is blocked; `gh api` (REST) works everywhere.

New issues are labeled automatically by `.github/workflows/triage.yml`; the operator runbook is [triage-runbook.md](triage-runbook.md) and the label vocabulary is [triage-labels.md](triage-labels.md).

## Conventions

- **Create an issue**: use the GitHub MCP tools if the session has them; otherwise `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue with its comments and labels**: use the GitHub MCP tools if the session has them; otherwise `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: use the GitHub MCP tools if the session has them; otherwise `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: use the GitHub MCP tools if the session has them; otherwise `gh issue comment <number> --body "..."`
- **Apply / remove labels**: use the GitHub MCP tools if the session has them; otherwise `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close an issue with a comment**: use the GitHub MCP tools if the session has them; otherwise `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v` and pass owner and repo to the MCP tools; `gh` does this automatically when run inside a clone.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature requests; `/triage` reads this flag.)_

When set to `yes`, PRs run through the same labels and states as issues, with the pull-request equivalents (the GitHub MCP tools if the session has them; otherwise `gh pr`):

- **Read a PR with its comments and diff**: use the GitHub MCP tools if the session has them; otherwise `gh pr view <number> --comments` and `gh pr diff <number>` for the diff.
- **List external PRs for triage**: use the GitHub MCP tools if the session has them; otherwise `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments` then keep only `authorAssociation` of `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, or `NONE` (drop `OWNER`/`MEMBER`/`COLLABORATOR`).
- **Comment / label / close a PR**: use the GitHub MCP tools if the session has them; otherwise `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

GitHub shares one number space across issues and PRs, so a bare `#42` may be either — resolve it by reading it as a PR first and as an issue second. Use the GitHub MCP tools if the session has them; otherwise `gh pr view 42`, falling back to `gh issue view 42`.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Read the issue with its comments. Use the GitHub MCP tools if the session has them; otherwise `gh issue view <number> --comments`.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. Create it with that label: use the GitHub MCP tools if the session has them; otherwise `gh issue create --label wayfinder:map`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (`gh api` on the sub-issues endpoint). Where sub-issues aren't enabled, add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: GitHub's **native issue dependencies** — the canonical, UI-visible representation. Add an edge with `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, where `<blocker-db-id>` is the blocker's numeric **database id** (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _not_ the `#number` or `node_id`). GitHub reports `issue_dependencies_summary.blocked_by` (open blockers only — the live gate). Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is closed.
- **Frontier query**: list the map's open children scoped to the map's sub-issues / task list (use the GitHub MCP tools if the session has them; otherwise `gh issue list --state open`), drop any with an open blocker (`issue_dependencies_summary.blocked_by > 0`, or an open issue in the `Blocked by` line) or an assignee; first in map order wins.
- **Claim**: assign the ticket to yourself — the session's first write. Use the GitHub MCP tools if the session has them; otherwise `gh issue edit <n> --add-assignee @me`.
- **Resolve**: comment the answer on the ticket, then close it (use the GitHub MCP tools if the session has them; otherwise `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`), then append a context pointer (gist + link) to the map's Decisions-so-far.
