# ADR-0023: The PR review model reads a checkout of the base commit

## Status

Accepted (2026-11-26) by the maintainer (#1000). Partly supersedes
[ADR-0012](0012-pr-review-on-claude-subscription.md): its "without tools"
and "an empty temporary working directory", and the consequence that rests
on them, "No tool means a prompt injection … hence the explicit flags and the
empty directory". Every other part of ADR-0012 stands: the subscription
token, the unmodified and pinned CLI, the replaced system prompt and the
flags that load no settings, hooks or MCP servers.

## Context

The review model saw only the sanitized, capped diff and the base contents
of the changed files. On PR #990 the diff changed a rule (the triage bot also
sets `ready-for-human`, [ADR-0021](0021-triage-sets-ready-for-human.md)).
Two unchanged files still stated the old rule, `AGENTS.md` and
`docs/factory/architecture.md`; the review missed both. It also warned about
`scripts/issue_triage_prompt.md`, which was not in the diff, and said itself
that it could not inspect that file. The prompt held no such statement. A
grep of the base tree for the old wording finds both real cases.

The issue triage already gives its model a read-only checkout through the
same function, `pr_review_claude.run_claude`
([ADR-0013](0013-automated-issue-triage.md)).

## Decision

The `review` job of `.github/workflows/factory-pr-review.yml` checks out the
caller a second time, into `pr-review-base`, after the setup command, with
`persist-credentials: false` and without `ref:`. `pr_review.py --workspace
pr-review-base` hands that directory to `run_claude`, which runs

```text
claude --print --output-format json --tools Read,Grep,Glob --restricted
       --system-prompt <prompt> --model <model> --max-turns 10
       --no-session-persistence --strict-mcp-config --disable-slash-commands
       --setting-sources ""
```

with `pr-review-base` as its working directory and no `--add-dir`. Without
`--workspace` (a local run) the call stays tool-less as in ADR-0012.

`scripts/pr_review_prompt.md` names every workspace file untrusted and adds
one rule: when the diff changes a rule, a label, a state or an ADR decision,
grep the workspace for the old wording and report each unchanged file that
still states it, but only after reading that file.

The workflow change reaches other callers at their next pin bump; there is
no input to turn it off.

## Why a read-only base tree is safe

- **Tools.** Read, Grep and Glob only. No Bash, Edit, Write, WebFetch or
  WebSearch; `--strict-mcp-config` without a config loads no MCP server and
  `--disable-slash-commands` no command. Injected text can still sway the
  verdict, as before, but cannot run a command, write a file or reach the
  network.
- **Confinement.** `--restricted` confines the file tools to the working
  directory and refuses `/proc/self/environ` and symlinks that resolve
  outside it (checked for the pinned 2.1.321, ADR-0013). The token stays in
  the process environment, out of reach; so do `context.json` and
  `review.json` one directory up. An answer that contains the token is still
  refused before it can be published.
- **The base commit, never the head.** Without `ref:` the checkout is
  `github.sha`: on `pull_request_target` the last commit of the pull
  request's base branch, on a manual run the commit of the ref it was
  started from, which needs write access. Every commit in it was pushed to
  this repository by someone with write access, and fork pull requests never
  reach the `review` job. The head's changes arrive only as the diff in the
  payload. `test_no_job_checks_out_the_pull_request_head` still finds no
  `ref:` or `repository:` on any checkout.
- **What `setup_command` can have written.** It runs in the first checkout
  (`$GITHUB_WORKSPACE`), before `pr-review-base` is checked out, without the
  model token and with no credential in that checkout's git config. This
  repository and repo-maintenance pass none. Dotfiles passes
  `scripts/install-runner-standards.sh`: it clones this repository into a
  `mktemp` directory it deletes on exit and installs the agent instructions
  under the runner's home (`~/.claude/`, `~/.agents/instructions/`). Both
  are outside `pr-review-base` and outside the restricted directory. A
  command that created `pr-review-base` first would have it emptied by
  `actions/checkout` (or cleaned with `git clean -ffdx` and reset, if it
  were a clone of the same repository) before the checkout.
- **Settings in the tree.** The base tree holds this repository's
  `.claude/settings.json` hooks and `CLAUDE.md`. `--setting-sources ""` and
  the replaced system prompt keep them unloaded, as in the triage call.

## Considered options

- **Reuse the caller checkout, as the triage does.** Rejected: in the
  review job it also holds `context.json`, which carries the head's diff,
  `review.json`, and whatever `setup_command` wrote into it.
- **Check out `github.event.pull_request.base.sha`.** Rejected: a `ref:` on
  a checkout is the one place a head ref could slip in, and the head-checkout
  test flags every `ref:`. A manual run has no event pull request either. The
  price is in the consequences.
- **Send more base files in the payload.** Rejected: which unchanged files
  state the old rule is the question; only a search of the tree answers it.
- **Stay tool-less (ADR-0012).** Rejected: the misses on PR #990.

## Consequences

- A review may take up to 10 turns and 600 seconds instead of one turn and
  300 seconds, so each one draws more on the subscription. ADR-0012's reopen
  condition (reviews crowding out interactive use) now weighs more. The cap is
  10, not 40, because reviews share the subscription's 5-hour limit, which about
  30 tool-less reviews already reached on 2026-11-26; 10 turns leave room for
  the few searches and reads the PR #990 case needed.
- The workspace is the base branch's tip when the run starts; the payload's
  base contents are from the pull request's base commit. When the base branch
  moved after the last push, the two differ.
- Bumping the CLI pin now also bumps the review's sandbox: rerun the ADR-0013
  check (Read and Grep outside the directory, a `/proc` link, a directory
  link must all be refused) before the bump.
- A pointer in a standards file can be followed when its target is in the
  base tree; one outside it (such as `~/.agents/instructions/`) still cannot.
