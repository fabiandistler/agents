# Using the skills

How the installed skills fire, how to invoke the ones that do not fire on their
own, and what else the catalogue installs next to them. Installing is in
[`install.md`](install.md).

**Skills fire on their description.** Most skills are model-triggered: the
agent reads the one-paragraph `description` in every `SKILL.md` and loads the
body when a request matches. You do not name them.

**Two categories go through a router.** `architecture` and `ai-ml` register a
single broad entry point that routes to the right sub-skill, so the category
costs one trigger entry instead of one per sub-skill. Members live under the
router's `members/` directory and load only when routed to. Ask for the
situation, not for a member: the router loads and reads the member itself. A
member has no registered name of its own, so do not expect `/architecture:ddd`;
on Claude the registered entry is the router.

**Command skills are invoked explicitly.** Skills marked `activation: command`
are user-invoked only and install as commands. In Claude Code they carry the
plugin namespace:

- `/refactoring:improve-codebase`
- `/workflow:oss-scouting`
- `/workflow:poc-spec-loop`
- `/workflow:pypet-snippets`
- `/workflow:release-pr`
- `/workflow:repo-status`
- `/communication:tldr`
- `/communication:was`

OpenCode discovers them as `/name` slash commands from the ordinary skill
directory through `opencode/slash` and `opencode/autoinvoke` metadata. Codex
gets them as skills that run only on an explicit `$name`, such as
`$oss-scouting`. The list above is hand-maintained; `skills.json` records
`activation: command` for each one.

**Shared rules are separate from skills.** Skills are capabilities loaded on
demand. `instructions/` has three tiers: always-on rules, Claude path-scoped
rules, and on-demand rules whose pointers stay in the global instruction file.
`./install.sh --instructions` composes the always-on rules and pointers into
`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` or
`~/.config/opencode/AGENTS.md`, and installs the on-demand files under
`~/.agents/instructions/`. Claude loads path-scoped rules only for matching
files; the installer and this repo's cloud mirror add a Claude hook that
supplies the Python baseline before `uv init`. Content outside the managed
markers is never touched.

**Only the human merges.** No interactive agent merges a pull request or
enables auto-merge. A pre-tool hook blocks both: the `merge-guard` plugin in
Claude Code, `./install.sh --merge-guard` for Codex CLI and opencode. This repo's
`.claude/settings.json` carries the same hook for cloud sessions. Details and limits:
[docs/install-optional-components.md](install-optional-components.md#pr-merge-guard---merge-guard).

One exception, in this repository only ([ADR-0011](adr/0011-pr-review-merge-exception.md)):
the model-free `publish` job of `.github/workflows/pr-review.yml` may enable
GitHub's native auto-merge on a docs-only pull request. Docs-only means
`risk:low`: only `docs/**` outside `docs/agents/` and `docs/adr/`,
`GLOSSARY.md`, `MAINTENANCE.md` or `maintenance/reports/**`, with no deletion,
no rename and within the size limits; `README.md` and ADRs are excluded. It
also needs a complete `review:pass`, a same-repository non-draft pull request
to `main`, no `do-not-merge`, and the repository variable `PR_AUTO_MERGE` set
to `true`. GitHub then merges only after the required checks `checks`,
`bats`, `mermaid`, `secrets` and `pr-review/verdict` pass; the last is the
commit status the `publish` job sets once any verdict exists for the head, so
every merge waits for the review without the review becoming a gate. The bot
never merges directly, and the merge
guard still stops any agent session from doing what that job does. Operation:
[docs/agents/pr-review-runbook.md](agents/pr-review-runbook.md).
The `secret-guard` plugin (`--secret-guard`) likewise blocks reading credential
files and dumping the environment:
[docs/install-optional-components.md](install-optional-components.md#secret-read-guard---secret-guard).

**Reading without installing.** [`skills.json`](../skills.json) is the generated
machine-readable manifest: `scripts/build_manifest.py` writes it from each
`SKILL.md`, so do not edit it by hand. It carries a `version` and a `skills`
array whose entries hold `name`, `category`, `path`, `summary` and
`activation` (`auto` is omitted because it is the default), plus
`compatibility`, `version`, `environments` and `targets` when the skill
declares them. For an ordinary skill the `summary` is the description's first
sentence, truncated at 200 characters; for a router it is the whole
description, with `when_to_use` appended the way Claude does. Query it with
`jq`:

```sh
jq -r '.skills[] | [.category, (.activation // "auto"), .name] | @tsv' skills.json
```

[`AGENTS.md`](../AGENTS.md) is the agent-facing entry point with links to every
`SKILL.md`.
