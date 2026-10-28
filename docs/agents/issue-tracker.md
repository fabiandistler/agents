# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. For every operation below,
use the GitHub MCP tools if the session has them; otherwise `gh api` against the
REST endpoint. GraphQL-backed `gh` porcelain (`gh issue`, `gh pr`, `gh search`,
`gh label`, `gh repo view`, `gh release list|view`) fails with HTTP 403 in
Claude Code cloud sessions; REST works everywhere.

Inside a clone, `gh` replaces `{owner}` and `{repo}` in the endpoint. Pass owner
and repo explicitly to the MCP tools.

## Conventions

- **Create an issue**: use the GitHub MCP tools if the session has them;
  otherwise `gh api --method POST repos/{owner}/{repo}/issues -f title="..."
  -F body=@- < body.md`. `-F body=@-` reads a multi-line body from stdin.
- **Read an issue with its comments and labels**: use the GitHub MCP tools if
  the session has them; otherwise read the issue and its comments separately:

  ```bash
  gh api repos/{owner}/{repo}/issues/<number> \
    --jq '{number, title, body, labels: [.labels[].name]}'
  gh api --paginate repos/{owner}/{repo}/issues/<number>/comments \
    | jq -s 'add | map({author: .user.login, body})'
  ```

- **List issues**: use the GitHub MCP tools if the session has them; otherwise:

  ```bash
  gh api --paginate "repos/{owner}/{repo}/issues?state=open&labels=<label>" \
    | jq -s 'add | map(select(.pull_request == null)
      | {number, title, body, labels: [.labels[].name]})'
  ```

  The REST issues endpoint also returns pull requests, hence the filter. It does
  not embed comments; read an issue when you need them.
- **Comment on an issue**: use the GitHub MCP tools if the session has them;
  otherwise `gh api --method POST repos/{owner}/{repo}/issues/<number>/comments
  -F body=@- < comment.md`.
- **Apply / remove labels**: use the GitHub MCP tools if the session has them;
  otherwise `gh api --method POST repos/{owner}/{repo}/issues/<number>/labels
  -f "labels[]=<label>"` and `gh api --method DELETE
  repos/{owner}/{repo}/issues/<number>/labels/<label>`.
- **Close an issue with a comment**: comment first (above), then use the GitHub
  MCP tools if the session has them; otherwise `gh api --method PATCH
  repos/{owner}/{repo}/issues/<number> -f state=closed`.

## Pull requests

External PRs are not a triage surface in this repo: the labels and states above
apply to issues only. GitHub shares one number space across issues and PRs, so a
bare `#42` may be either. Read it as a PR first
(`gh api repos/{owner}/{repo}/pulls/42`), then as an issue
(`gh api repos/{owner}/{repo}/issues/42`).

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Read the issue with its comments.

## Wayfinding operations

Claude Code sessions in this repo only: `wayfinder` is a vendored skill under
`.claude/skills/`, not a catalogue skill, so it is absent on Codex CLI and
opencode. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes /
  Decisions-so-far / Fog body. Create it with that label: use the GitHub MCP
  tools if the session has them; otherwise `gh api --method POST
  repos/{owner}/{repo}/issues -f title="<map title>" -f "labels[]=wayfinder:map"
  -F body=@- < map.md`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue
  (`gh api --method POST repos/{owner}/{repo}/issues/<map>/sub_issues -F
  sub_issue_id=<child-db-id>`). Where sub-issues aren't enabled, add the child
  to a task list in the map body and put `Part of #<map>` at the top of the
  child body. Labels: `wayfinder:<type>`
  (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is
  assigned to the driving dev.
- **Blocking**: GitHub's **native issue dependencies** — the canonical,
  UI-visible representation. Add an edge with `gh api --method POST
  repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F
  issue_id=<blocker-db-id>`, where `<blocker-db-id>` is the blocker's numeric
  **database id** (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _not_ the
  `#number` or `node_id`). GitHub reports
  `issue_dependencies_summary.blocked_by` (open blockers only — the live gate).
  Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>`
  line at the top of the child body. A ticket is unblocked when every blocker is
  closed.
- **Frontier query**: list the map's open children with `gh api
  repos/{owner}/{repo}/issues/<map>/sub_issues`, or its task list where
  sub-issues aren't enabled; drop any with an open blocker
  (`issue_dependencies_summary.blocked_by > 0`, or an open issue in the
  `Blocked by` line) or an assignee; first in map order wins.
- **Claim**: assign the ticket to yourself — the session's first write. Use the
  GitHub MCP tools if the session has them; otherwise `me=$(gh api user --jq
  .login)` and `gh api --method POST
  repos/{owner}/{repo}/issues/<n>/assignees -f "assignees[]=$me"`.
- **Resolve**: comment the answer on the ticket, then close it
  (`gh api --method POST repos/{owner}/{repo}/issues/<n>/comments -F body=@-
  < answer.md`, then `gh api --method PATCH
  repos/{owner}/{repo}/issues/<n> -f state=closed`), then append a context
  pointer (gist + link) to the map's Decisions-so-far: read
  `gh api repos/{owner}/{repo}/issues/<map> --jq .body`, append the line, and
  send the result back with `gh api --method PATCH
  repos/{owner}/{repo}/issues/<map> -F body=@-`.
