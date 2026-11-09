# ADR-0012: The PR review runs on the Claude subscription through the Claude Code CLI

## Status

Accepted (2026-11-09) by the maintainer. Replaces the OpenCode Zen provider
of the PR review pipeline (#621, #635). [ADR-0011](0011-pr-review-merge-exception.md)
is unchanged: the model still only advises.

## Context

The `review` job of `.github/workflows/pr-review.yml` called OpenCode Zen's
OpenAI-compatible API with an `OPENCODE_API_KEY`. OpenCode's documentation
asks for billing details before it issues a key, even for the free models, and
those free models are offered for a limited time. The maintainer has no such
key and wants no paid account for it; every review was `review:unavailable`.

The maintainer already pays for a Claude subscription, and `claude.yml`
already holds its token as `CLAUDE_CODE_OAUTH_TOKEN`.

Anthropic's terms, checked 2026-11-09:

- [Authentication](https://code.claude.com/docs/en/authentication):
  `claude setup-token` creates a one-year OAuth token "for CI pipelines,
  scripts, or other environments where interactive browser login isn't
  available".
- [Legal and compliance](https://code.claude.com/docs/en/legal-and-compliance):
  subscription OAuth supports "ordinary use of Claude Code and other native
  Anthropic applications"; signing in to "the unmodified Claude Code binary
  with their own Claude subscription" is allowed; routing requests through
  plan credentials elsewhere is not, and "advertised usage limits … assume
  ordinary, individual usage".

## Decision

`scripts/pr_review.py` keeps building, sanitizing and capping the request and
keeps parsing the answer. Only the transport changes: instead of an HTTP call
it runs the pinned, unmodified Claude Code CLI once,

```text
claude --print --output-format json --tools "" --system-prompt <prompt>
       --model <PR_REVIEW_MODEL or sonnet> --max-turns 1
       --no-session-persistence --strict-mcp-config --disable-slash-commands
       --setting-sources ""
```

with the payload on stdin, `CLAUDE_CODE_OAUTH_TOKEN` in its environment and an
empty temporary working directory. The workflow installs
`@anthropic-ai/claude-code` at an exact version in a step that does not see
the token.

## Considered options

- **Subscription token sent straight to the API from `pr_review.py`.**
  Rejected: outside the Claude Code binary this routes plan credentials
  through another client, which the terms forbid and Anthropic enforces.
- **`anthropics/claude-code-action`.** Rejected: it runs an agent with tools
  and GitHub write paths in the job that holds the token. The pipeline's
  split (model job read-only, publisher model-free) would be lost.
- **OpenRouter free models.** Viable fallback: an OpenAI-compatible API, so
  the old HTTP transport would need only a new base URL and key; 50 free
  requests a day (1000 after a one-time USD 10 purchase). Not chosen: free
  models rotate like Zen's, their quality is lower, and many require allowing
  training on prompts.
- **GitHub Models** (no extra secret). Unavailable: GitHub has retired it.
- **Keep OpenCode Zen.** Rejected: it needs a paid account.

## Consequences

- Reviews draw on the maintainer's subscription limits, shared with
  interactive use. Forks are never reviewed, so no outsider spends them.
- No tool means a prompt injection in the diff can sway the verdict but not
  run commands or read the token; `--bare` is not an option because it
  ignores the OAuth token, hence the explicit flags and the empty directory.
- Two manual chores: renew the token yearly, and bump the pinned CLI version
  by hand (Dependabot does not see an `npm install` line). Both are in the
  [runbook](../agents/pr-review-runbook.md#model-change).
- Reopen this decision if Anthropic narrows CI use of subscription tokens, or
  if the reviews crowd out interactive use.
