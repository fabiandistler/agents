# ADR-0017: The Retro task proposes changes to the factory's instruction texts

## Status

Proposed (2026-11-14). Builds on
[ADR-0014](0014-agent-runs-in-github-actions.md) (agent runs in GitHub
Actions with the Claude GitHub App token) and
[ADR-0011](0011-pr-review-merge-exception.md) (the review bot's auto-merge).

## Context

The implementer opens pull requests, the PR review comments on them, Rework
rounds fix the findings, and the maintainer fixes the rest by hand before the
merge. After the merge nothing reads that trail. The `retro` skill
(`.claude/skills/retro/`) exists for interactive sessions only, and the
implementer's run summary lived only on its run page. The same mistakes recur
because the review prompt, the triage prompt, the runbooks and `AGENTS.md`
never learn from them.

## Decision

A workflow `.github/workflows/retro.yml` runs daily and by hand. It looks at
one merged agent pull request when about ten have merged since the last retro,
and proposes changes to the factory's own instruction texts as one pull
request. Procedure and PR body format: [`docs/agents/retro.md`](../agents/retro.md).

- **Clock trigger, not a merge trigger.** A merge would need
  `pull_request_target` (`pull_request` on a closed event runs with the
  merged branch's workflow file), which GitHub blocks by default in public
  repositories from 2026-12-02 (#763). An auto-merge by the review bot is a
  `GITHUB_TOKEN` write and starts no workflow at all (ADR-0011), so those
  merges would be missed. A daily run with a counter catches both.
- **Throttle and counter on the git host.** The gate,
  `scripts/retro_gate.py`, counts merged `agent/issue-<n>` pull requests since
  the newest one labelled `retro:done`. Below `RETRO_EVERY` (default 10) it
  ends. It labels the selected pull request before the model job starts, so
  the counter lives on GitHub, needs no state file, and a failed model run
  does not repeat on the same pull request.
- **Eligibility floor.** Only pull requests merged after the commit that
  added `retro.yml` count. The pull requests merged before (20 on 2026-11-13)
  were made under older prompts; a backlog sweep would spend runs on lessons
  already learned. An unreadable floor fails the gate rather than counting
  from the start.
- **Selection.** The pending pull request with the most non-pass review
  rounds, the newest on a tie: that is where the factory's texts failed most.
- **Path allowlist.** The model edits only the review prompt, the triage
  prompt, runbooks under `docs/agents/`, and `AGENTS.md`. Vendored files (any
  path `.gitattributes` marks `linguist-vendored`) are excluded: a re-vendor
  overwrites them (`scripts/vendor_mattpocock_skills.py`), so a local edit
  would vanish silently. A change wanted there, or in a workflow file the App
  token cannot write, goes into the PR body as proposed text.
- **`No issue: <reason>. Refs #<pr>`.** A Retro pull request closes no issue.
  The PR issue-link check requires a closing declaration or an explicit "no
  issue"; the first line gives the latter. No closing keyword may stand before
  an issue reference anywhere in the body, quoted text included: the merge of
  #795 closed an unrelated issue that way.
- **Trusted text only.** The context file holds text by owners, members and
  collaborators, the review bot and the Claude App, and the issue contract
  read as the implementer reads it. An outsider's comment never reaches the
  model that holds a write token. The rule is about authors: the App's own
  pull request body and commits can repeat text the implementer read, so the
  model treats the whole context file as data, not instructions.
- **Model.** The skill audit's alias (`sonnet`), overridable by the
  `RETRO_MODEL` variable. A retro reads one pull request and edits prose, and
  runs about once per ten merges, so it costs little of the subscription
  shared with interactive use, the implementer, the review and the triage.
- **Security posture.** The gate job is model-free and holds the
  `GITHUB_TOKEN` with `pull-requests: write`, `issues: write` (the label),
  `actions: read` (the implementer's run summary) and `contents: read`. The
  model job holds the App token, because only its pull requests start CI and
  the PR review, and a job token that stays read-only.

## Considered options

- **A merge trigger.** Rejected: blocked by default from 2026-12-02 and blind
  to the bot's auto-merges.
- **A retro of every merge.** Rejected: one run per merge would cost more than
  the lessons are worth and would open overlapping pull requests.
- **Editing the vendored triage guidance directly.** Rejected: the next
  re-vendor would revert it.

## Consequences

- The workflow file is added by hand: the App token cannot write
  `.github/workflows/`. Its commit sets the floor.
- The implementer uploads its run summary as an artifact and names its run
  after the issue, so the gate finds the summary. Artifacts expire; a retro of
  an old pull request runs without one.
- The Retro pull request goes through the PR review and the human merge like
  any other.
