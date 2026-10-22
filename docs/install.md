# Installing

Per-agent detail behind `install.sh`. The [README](../README.md) covers the
two normal paths; this page answers *what exactly did it write, and how do I
undo it* — read it when an install touched a config file you maintain by hand,
or when you want a subset of the catalogue.

Everything here is reversible with the same command plus `--uninstall`, and
every command accepts `--dry-run`.

## What gets linked where

| Target | Skills | Command skills (`activation: command`) |
|---|---|---|
| `claude` | `~/.claude/skills/<skill>` | `~/.claude/commands/<name>.md` |
| `codex` | `~/.agents/skills/<skill>` | `~/.agents/skills/<skill>` (see below) |
| `opencode` | `~/.config/opencode/skills/<skill>` | `~/.config/opencode/command/<name>.md` |

Only top-level skills are linked. A category with a router (`architecture`,
`ai-ml`) links the router alone — its members live under `members/` and load
lazily when the router routes to them.

The installer prunes as it goes: a dangling symlink pointing at a skill this
repo no longer ships is removed on the next install or uninstall, and a flat
link left by a pre-router install is removed on both paths. Symlinks pointing
outside this repo are never touched.

## Selecting a subset

**By category.** Every `SKILL.md` carries a `category` field — one of
`architecture`, `refactoring`, `ai-ml`, `workflow`, `communication`,
`personal`. It decides the catalogue section, the `--category` subset, and
which plugin bundles the skill.

```sh
./install.sh --target=claude --category=architecture
./install.sh --target=codex  --category=refactoring,workflow
```

**By environment.** Each skill is tagged `environments: coding`, `chat`, or
both, so a chat app gets the chat skills and a coding agent the coding ones. A
skill without the field belongs to every environment.

```sh
./install.sh --target=claude --env=coding
./install.sh --target=claude --env=chat
```

**Skills that skip an agent.** A skill can opt out of individual agents with a
`targets` field (a comma-separated subset of `claude`, `codex`, `opencode`;
absent means all of them). `install.sh` never links it for an excluded agent
and removes a link it created there before — use it when a runtime already
ships an equivalent of its own. Because `plugins/` is the Claude distribution
of these skills, a skill that excludes `claude` also gets no plugin symlink.

## Shared instructions (`--instructions`)

Skills are capabilities an agent loads on demand; the rules that should apply
to *every* session are something else. Those live in `instructions/` as
single-topic Markdown fragments, ordered by their numeric filename prefix.

```sh
./install.sh --target=all --instructions             # sync the rule files
./install.sh --target=all --instructions --dry-run   # preview
./install.sh --target=all --instructions --uninstall # strip the block
```

Each fragment is authored once and composed into a marker-delimited managed
block in the agent's global instruction file — `~/.claude/CLAUDE.md` for Claude
Code, `~/.codex/AGENTS.md` for Codex CLI, `~/.config/opencode/AGENTS.md` for
opencode. The filenames differ because that is
what each agent reads; the content is one AGENTS.md-style document either way.
A fragment may limit itself to some agents with a `targets:` frontmatter field,
exactly as a skill does.

A fragment with a `paths:` field (comma-separated globs, e.g.
`paths: **/*.R, **/DESCRIPTION`) leaves Claude's block and is written as a
[path-scoped rule](https://code.claude.com/docs/en/memory#path-specific-rules)
to `~/.claude/rules/agents-<fragment>.md`, which Claude Code loads only once it
reads a matching file. Codex and opencode have no equivalent and keep the
fragment in their block. Rule files without the `managed-by:` line are never
touched. The catch: nothing loads before the first matching read, so a rule that
must hold while *creating* the first such file does not belong behind `paths:`.

Anything outside the markers is left alone, so hand-written notes and
`@`-imports survive install, reinstall, and uninstall. Unbalanced markers (from
a hand edit) make the installer skip the file rather than guess.

opencode reads `~/.claude/CLAUDE.md` only as a fallback when
`~/.config/opencode/AGENTS.md` does not exist
([rules](https://opencode.ai/docs/rules)), and opencode V2 drops that fallback
([instructions](https://opencode.ai/v2/docs/instructions)), so it gets a file of
its own and no rule loads twice. Once that file exists, opencode stops reading
`~/.claude/CLAUDE.md`: anything you wrote there outside the markers and want in
opencode too belongs in `~/.config/opencode/AGENTS.md` as well.

The flag is opt-in — plain `./install.sh --target=...` only touches skills.

## PR merge guard (`--merge-guard`)

Coding agents act under your GitHub account, so branch protection and required
approvals do not stop them from merging their own pull requests. In this repo
that led to 22 PRs merged on red CI and 30 reverted merges (#557). The merge
guard is a model-free pre-tool hook: before each shell or MCP tool call it runs
[`scripts/pr_merge_guard.py`](../scripts/pr_merge_guard.py), which blocks the
call and tells the agent to ask you to merge.

```sh
./install.sh --target=all --merge-guard             # install for every agent
./install.sh --target=all --merge-guard --dry-run   # preview
./install.sh --target=all --merge-guard --uninstall # remove it again
```

It blocks `gh pr merge` (including `--auto`), `gh api` or `curl` writes to
`repos/<o>/<r>/pulls/<n>/merge` and `repos/<o>/<r>/merges`, the GraphQL
mutations `mergePullRequest`, `enablePullRequestAutoMerge` and
`enqueuePullRequest`, and MCP tools named `merge_pull_request` or
`enable_pr_auto_merge`. GitHub has no REST endpoint for auto-merge. Reads pass:
`gh pr view`, `gh pr checks`, a local `git merge`. To merge, use the GitHub web
UI or your own terminal. The guard only checks the agent's tool calls.

| Agent | What the installer writes | Hook |
|---|---|---|
| `claude` | one `PreToolUse` entry in `~/.claude/settings.json`, found again by the script name in its command | [PreToolUse](https://code.claude.com/docs/en/hooks), exit 2 blocks |
| `codex` | a managed `[[hooks.PreToolUse]]` block in `~/.codex/config.toml` | [PreToolUse](https://developers.openai.com/codex/hooks), exit 2 blocks |
| `opencode` | symlink `~/.config/opencode/plugins/pr-merge-guard.js` | [`tool.execute.before`](https://opencode.ai/docs/plugins/) (1.x) and `ctx.tool.hook("execute.before")` ([2.x](https://opencode.ai/v2/docs/build/plugins)); a throw blocks |

All other settings, hooks and config stay as they are. The hook needs
`python3` on `PATH` when it runs, and the hook command points into this
clone, so do not move the clone after installing.

Limits:

- **Codex** runs a new or changed non-managed hook only after you trust it.
  Open `/hooks` once after installing. Until then Codex skips the guard and
  warns at startup.
- **opencode** does not fire plugin hooks under headless `opencode run`
  ([anomalyco/opencode#41422](https://github.com/anomalyco/opencode/issues/41422))
  or in the Desktop app
  ([anomalyco/opencode#38604](https://github.com/anomalyco/opencode/issues/38604)),
  and may skip them for MCP tools in experimental code mode. The plugin's default
  export with `server()` needs opencode 1.18.29 or later.
- Hooks are a guardrail, not a security boundary. A command the parser does not
  recognize (a `gh` alias, a script file that calls `gh pr merge`) gets
  through. A required status check on `main` is still the backstop.

## Codex CLI specifics

For Codex, `--target=codex` covers the full plugins, not just the skills. It
needs `python3` (the extras are skipped with a warning otherwise); `--env`
filters skills only, while the extras follow `--category`.

**Subagents.** Each selected plugin's subagents (`coupling-analyst`,
`cohesion-analyst`) are converted into [Codex custom
agents](https://developers.openai.com/codex/subagents) under
`~/.codex/agents/<name>.toml`. The generated files carry a marker comment;
files you created yourself are never overwritten, and `--uninstall` removes
only marker-carrying files. Every Codex run also removes marker-carrying
files whose subagent no longer exists in the repo (renamed or deleted).
Model and sandbox are inherited from your Codex
session — the Claude-specific `model:` and `tools:` fields have no Codex
equivalent.

**Router members.** Codex discovers skills recursively and follows symlinks
([openai/codex#22275](https://github.com/openai/codex/issues/22275)), so each
`members/<name>/SKILL.md` would otherwise register as its own skill and the
router's progressive disclosure would be lost. The installer therefore disables
every nested member in `~/.codex/config.toml`, via a marker-delimited
`[[skills.config]]` block (`enabled = false`). Each entry selects the member by
`path`, the selector the [config
reference](https://learn.chatgpt.com/docs/config-file/config-reference)
documents, so a skill of your own with the same name stays enabled. The path
points into this clone, so re-run the install after moving it. `--uninstall`
removes the block.

**Skills directory.** Codex skills are linked into `~/.agents/skills/`, the
user scope [Codex documents](https://developers.openai.com/codex/skills);
`~/.codex/skills/` is read only for backward compatibility. Other tools install
into `~/.agents/skills/` too, so a skill name that is already taken there is
reported with a `WARN` line and skipped, never overwritten. Every Codex install
and uninstall removes the links an older version left in `~/.codex/skills/`
(only links that point into this repo), so no skill loads twice.

**Command skills.** Codex custom prompts are deprecated, so `activation:
command` skills install as regular skills under `~/.agents/skills/`. Each
carries an `agents/openai.yaml` sidecar with
`policy.allow_implicit_invocation: false`, so Codex runs them only on an
explicit `$skill-name`, never on its own. The installer also removes any
leftover `~/.codex/prompts/<name>.md` symlinks a previous version created.

**Legacy MCP cleanup.** Earlier versions registered a knowledge-base MCP server
per plugin. Those are gone — the skills' `references/` pages are read directly.
Both install and `--uninstall` strip whatever an older version left in
`~/.codex/config.toml` and remove its `~/.codex/agents-mcp-runtime` venv. Any
`[mcp_servers.*]` entries you added yourself are untouched.

Restart Codex to pick up the new agents.

## Claude plugins vs symlinks

The repo doubles as a Claude plugin marketplace: every category is packaged as
one plugin (see `plugins/` and
[`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json)), so
you can install exactly the domains you want. Plugin skills are namespaced
(`communication:documentation`); a routed category registers only its router,
so there it is the router that carries the namespace
(`architecture:architecture`).

In Claude Code, use either the plugins **or** the symlinks — with both at once
every skill appears twice.

## Cloud sessions (`.claude/` in this repo)

Claude Code cloud sessions start from a fresh clone: they never see
`~/.claude/`, and they do not install plugins a repository enables in
`.claude/settings.json`. So this repo commits what a cloud session in it
should have:

| Path | Contents | Maintained by |
| --- | --- | --- |
| `.claude/skills/<name>` | symlinks to this repo's `coding` skills (routers, unrouted skills, command skills) | `scripts/build_project_claude.py` |
| `.claude/agents/*.md` | symlinks to the plugins' subagents, next to the repo's own two | `scripts/build_project_claude.py` |
| `.claude/rules/agents-*.md` | `instructions/` rendered as rules; `paths:` fragments stay path-scoped, and are left out while no tracked file matches; `SKIPPED_FRAGMENTS` in the script lists fragments that never apply here | `scripts/build_project_claude.py` |
| `.claude/skills/<name>` (real dirs) | [mattpocock/skills](https://github.com/mattpocock/skills), its released plugin set plus `chief-of-staff` from `in-progress/`, pinned in `.claude/vendor/mattpocock-skills/lock.json` | `scripts/vendor_mattpocock_skills.py` |
| `.claude/settings.json` `PreToolUse` entry | the PR merge guard (`scripts/pr_merge_guard.py`); the rest of the file is hand-written | `scripts/build_project_claude.py` |
| `.claude/hooks/session-start.sh` | SessionStart hook (cloud only): installs the pinned check tools into a venv put first on `PATH`, fetches Go via `proxy.golang.org` for the gitleaks hook (the proxy blocks `go.dev`), runs `prek install` and `prek install-hooks` | by hand |

After changing a skill's frontmatter or an instruction fragment, the prek
commit hooks regenerate the manifest and `.claude/` (stage the result and
commit again); without them, regenerate the manifest and then run
`python3 scripts/build_project_claude.py`. CI fails on drift (`--check`). Refresh the vendored skills with
`python3 scripts/vendor_mattpocock_skills.py` (optionally `--ref <sha>`).
Upstream skills named in the script's `EXCLUDED` set are never vendored:
`improve-codebase-architecture` is left out because this catalogue forks it
as `improve-codebase` (#492), so cloud sessions offer one such command, not two.
`ask-matt` is left out because it was deleted by hand on 2026-10-13, and a re-run
would bring it back. Pocock's `pr` is vendored again since 2026-10-20 at the
user's request; the catalogue itself still ships no PR-description skill
(`.out-of-scope/pr-description-skill.md`).
`chief-of-staff` is still in upstream's `in-progress/` and is vendored anyway
(`INCLUDED_IN_PROGRESS`): it runs the long-lived goal sessions recorded in
`docs/wiki/`.

Locally the same project skills would duplicate the marketplace plugins, so
`.claude/settings.json` switches this repo's plugins (and `mattpocock-skills`)
off for sessions inside this repo only. The vendored `code-review` shadows
Claude Code's built-in skill of that name in this repo.
