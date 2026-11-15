# ADR-0019: Remove the `@claude` mention workflow

## Status

Accepted (2026-11-15) by the maintainer (#857).

## Context

`.github/workflows/claude.yml` ran `anthropics/claude-code-action` in tag mode
when a comment, review comment or review contained `@claude`. It was the only
agent workflow not built to the factory's contract
([ADR-0013](0013-automated-issue-triage.md),
[ADR-0014](0014-agent-runs-in-github-actions.md),
[ADR-0018](0018-reusable-factory-workflows.md)). On 2026-11-11 Depi published
an attack on OpenAI's Codex repository in which issue text passed to an agent
in Actions led to secrets read from the runner
([Depi](https://depi.security/blog/20261111-backdooring-codex/)).

Checked against the pinned action (`4fa93a8`, v1.0.271) on 2026-11-15:

- **Trigger gate.** Only an actor with write access starts a run. The model
  then reads the whole thread, and this repository is public: anyone can
  plant text in an issue, a pull request or a comment before the maintainer
  mentions `@claude`.
- **Token.** The action exchanges the job's OIDC token for a Claude GitHub App
  token with `contents: write`, `pull_requests: write` and `issues: write`
  (`src/github/token.ts:69-73`), whatever the job's `permissions` declare.
  The job's `contents: read` limited only `GITHUB_TOKEN`.
- **Token exposure.** The action stores that token in the checkout's origin
  URL (`src/github/operations/git-config.ts`, `replaceCheckoutCredentials`).
  Tag mode allows `Read` and `update_claude_comment`
  (`src/modes/tag/index.ts:162-171`), so an injected instruction could read
  `.git/config` and post the token in the tracking comment. No Bash is needed.
- **Push.** Tag mode allows `git add`, `git commit`, `git rm` and a push
  wrapper that accepts any valid branch name, `main` included
  (`scripts/git-push.sh`). The default-branch push guard does not recognise
  the wrapper.
- **Comment filter.** `include_comments_by_actor` filters comments, reviews
  and review comments (`src/github/data/fetcher.ts:342-560`), not the issue or
  PR body. An outsider's body still reaches the model.
- **Use.** Of the last 30 completed runs (2026-11-14 to 2026-11-15), one did
  work (run 762, 2026-11-14); the others were skipped. The factory workflows
  cover implementation, rework and review.

## Decision

Delete `claude.yml` and its test. `scripts/test_agent_action_triggers.py`
fails when any workflow runs `claude-code-action` on a comment or review event,
directly or through a local reusable workflow.

Comment-driven model work stays in the two patterns that hold up:

- a tool-less `claude -p` call whose output a model-free step publishes (the
  issue triage, ADR-0013; the PR review, ADR-0012);
- a model-free gate that starts the action from a contract written only by
  people with write access (the factory tasks, ADR-0014, ADR-0015, ADR-0018).

## Considered options

- **Harden in place.** Set `include_comments_by_actor`, deny `Read` on
  `.git/**`, teach the push guard the wrapper and load it through the
  `settings` input. Not chosen: it leaves the body injection open, adds a
  guard to maintain for a path used about once in two days, and the App
  token's scope stays broader than the job's.
- **`github_token: ${{ secrets.GITHUB_TOKEN }}`.** Scoped by the job's
  `permissions`, but the tracking comment and commits need `issues`,
  `pull-requests` and `contents` write, so the scope barely narrows, and its
  pushes start no checks (ADR-0014). Rejected.

## Consequences

- An `@claude` mention on GitHub no longer starts a run. Ad-hoc help on a pull
  request comes from an interactive Claude Code session or a `ready-for-agent`
  issue.
- Each new comment creates one workflow run fewer (only `issue-triage.yml`
  listens to comments now).
- `CLAUDE_CODE_OAUTH_TOKEN` stays: the factory workflows and the skill audit
  read it.
- The Claude GitHub App stays installed: the implementer, Rework and Retro
  exchange their OIDC tokens through it.
- To bring mentions back, open a new ADR that addresses the body injection and
  the token exposure above; the trigger test blocks a plain revert.
