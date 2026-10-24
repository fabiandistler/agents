# Installing

Per-agent detail behind `install.sh`. The [README](../README.md) covers the
two normal paths; this page answers *what exactly did it write, and how do I
undo it* — read it when an install touched a config file you maintain by hand,
or when you want a subset of the catalogue.

## Contents

- [Verify the install](#verify-the-install) and [Troubleshooting](#troubleshooting)
- [Exit codes](#exit-codes)
- [Check](#check-the-managed-installation), [replay](#replay-the-last-install) and [update](#update-after-a-merge-or-rebase)
- [Detect installed agents](#detect-installed-agents)
- [OpenCode subagents](#opencode-subagents)
- [What gets linked where](#what-gets-linked-where)
- [Selecting a subset](#selecting-a-subset)
- [Shared instructions](#shared-instructions---instructions)
- [PR merge guard](#pr-merge-guard---merge-guard) and [secret read guard](#secret-read-guard---secret-guard)
- [Codex CLI](#codex-cli-specifics) and [Claude Code](#claude-code-plugins-only)
- [Uninstall](#uninstall) and [maintainer notes](#maintainer-notes)

An install is reversed by the same command plus `--uninstall`; `--dry-run`
works on install, uninstall and `--update`, while `--check` rejects it.
`--update` replays the saved install and cannot be combined with
`--uninstall`.

Claude Code is the exception: it gets skills, commands, subagents and both
guard hooks from the plugin marketplace only, and `install.sh --target=claude`
only syncs `--instructions`. Remove those plugins with `claude plugin
uninstall`, not with `--uninstall`. See
[Claude Code: plugins only](#claude-code-plugins-only).

## Verify the install

`--check` verifies the installer's managed files, not that the runtime loaded a
skill. Verify the installer's state with `./install.sh --update --check` (or
repeat the flags you installed with), then the runtime separately per target:

- **Claude Code.** Open `/plugin` and confirm the marketplace
  `fabiandistler-agents` and the plugins you installed are listed. Run one
  namespaced command skill, such as `/communication:tldr`, and ask one
  question the catalogue covers. Plugin files live where Claude loaded the
  marketplace (its cache for a GitHub marketplace), not in `~/.claude/skills`.
- **Codex CLI.** Restart Codex and confirm the skill appears in its skill list.
  If a guard is installed, open `/hooks` once and trust it.
- **opencode.** Restart opencode and confirm the skill appears. If Codex is
  installed too, confirm the skill is listed once, not twice.

## Troubleshooting

| Symptom | Where to look |
|---|---|
| Skill missing in Claude Code | Is the marketplace added and the plugin installed? Check `/plugin`; see [Claude Code: plugins only](#claude-code-plugins-only). |
| Codex skill missing | Check `~/.agents/skills/` and the legacy `~/.codex/skills/`; restart Codex; run `--update --check`. |
| The same skill appears twice | Codex and opencode share `~/.agents/skills/`; see [What gets linked where](#what-gets-linked-where). |
| A guard hook does not fire | Codex skips an untrusted hook until you open `/hooks`; opencode does not run plugin hooks under `opencode run` or in the Desktop app. See the guard sections below. |
| A command skill does not fire on its own | Expected: command skills run only on explicit invocation (`$name` in Codex, `/name` in opencode, `/<plugin>:<name>` in Claude Code); see [Usage](../README.md#usage). |
| The Codex skill list looks incomplete | Codex truncates the skill list past roughly 2% of its context. Remove a category with `--category`, or disable unused skills. |
| `--update` exits 4 | No saved state. Run a successful install with `--target=...` first; see [Replay the last install](#replay-the-last-install). |
| `--check` reports `foreign` or `unbalanced` markers | An unmanaged file or a hand-edited managed block blocks the path. See the report states under [Check the managed installation](#check-the-managed-installation). |
| The install prints a `python3` warning, or `--update` says it is required | `python3` is missing: `--update` cannot read its state, and subagents, a guard hook, or the Claude `uv init` hook are skipped. Install it and re-run. |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | The requested operation succeeded. `--help` returns 0, as does `--check` when the selected installation is clean. |
| `1` | An operational failure prevented completion, such as an invalid saved-state file, a failed managed-file write, or an unusable `--output` path. |
| `2` | Invocation error: a missing or invalid target, an unknown option, incompatible options, a missing `--output` value, or `--target=detected` finding no installed agents. |
| `3` | `--check` found drift. When `--output` is supplied, the TSV report contains the drift rows. |
| `4` | `--update` found no saved install state. Run a successful install with `--target=...` before using `--update`. |

## Check the managed installation

`--check` runs the selected install calculation without changing managed files.
It prints a summary by default and exits with 0 when clean, 3 when it finds
drift, or 2 when the options are invalid. Add `--output FILE` to write the full
TSV report (`target`, `kind`, `path`, `state` columns):

```sh
./install.sh --target=all --check
./install.sh --target=codex --merge-guard --secret-guard --check --output /tmp/agents-drift.tsv
```

The report states are `missing` (expected managed state is absent), `stale`
(managed content no longer matches this checkout), `foreign` (an unmanaged
file or unbalanced marker blocks the managed path), `duplicate` (more than one
managed block or link occupies the selected state), and `untrusted-hook` (Codex
will skip a guard that is disabled or whose saved trust hash does not match its
current hook). Lowercase `missing` is this report state; uppercase `MISSING` in
`scripts/check_all.sh` means a check's tool is not installed.
Passing a guard flag makes that guard part of the expected state; existing
Codex guard blocks are checked for stale checkout paths and hook trust even
without a guard flag. Pass `--instructions`, `--merge-guard`, and
`--secret-guard` to include those optional components in the expected state.

## Replay the last install

Each successful install saves its resolved targets, filters, optional components,
and checkout path to `${XDG_STATE_HOME:-~/.local/state}/fabiandistler-agents/install.json`.
`--update` replays those options and rebases marker-owned paths and managed links
if this checkout moved. It exits 4 when no state file exists; start with an
install such as `./install.sh --target=codex`. `--update --dry-run` previews the
replay without changing files or state, and `--update --check` reports drift
against the saved options. During `--update`, every write re-checks its file
right before writing and leaves it alone if it changed in between.

## Update after a merge or rebase

`--git-hook` installs marker-owned `post-merge` and `post-rewrite` hooks in this
clone's Git hooks directory. They check the saved install first and run
`--update` only when the check finds drift. `post-rewrite` also consumes Git's
rewrite list, so it works after `git pull --rebase`. Hook setup is opt-in and
does not add a CI or prek stage:

```sh
./install.sh --target=all --git-hook
./install.sh --uninstall --git-hook
```

The targetless uninstall removes only these marker-owned hooks; it leaves the
global skill and instruction installation in place. Foreign hooks are skipped.

Git shares one hooks directory across a clone and its linked worktrees, so
`--git-hook` run from a linked worktree writes there too. The hooks record the
checkout that installed them and exit silently in every other worktree; a merge
in a worktree therefore never moves your links into a directory that
`git worktree remove` later deletes. When `core.hooksPath` is set (husky,
lefthook, a shared hooks directory), `--git-hook` refuses with exit 1 before
writing anything: that directory belongs to the hook manager, so call
`./install.sh --update` from it yourself.

## Detect installed agents

`--target=detected` selects an agent when its command is on `PATH` or its user
configuration directory exists: `claude` or `~/.claude/`, `codex` or
`~/.codex/`, and `opencode` or `~/.config/opencode/`. The installer prints the
resolved targets and saves that explicit list for later checks and updates, so
an agent installed after that run is neither added nor reported by `--update
--check`. Re-run `./install.sh --target=detected` to include it. A bare
`./install.sh` still writes nothing and exits 2; pass a target or use
`--target=detected` explicitly.

## OpenCode subagents

When OpenCode is selected, plugin subagents from `plugins/*/agents/*.md` are
rendered into `~/.config/opencode/agents/<name>.md`. The renderer keeps each
description and prompt, sets `mode: subagent`, maps Claude tools to OpenCode
permissions, and denies editing unless the source lists `Edit` or `Write`. It
drops Claude's `model` value and resolves `${CLAUDE_PLUGIN_ROOT}` for this
checkout. Generated files carry an ownership comment; stale generated files
are pruned, and uninstall removes only generated files for selected categories.
See the [OpenCode agent format](https://opencode.ai/docs/agents). The Codex
TOML and the OpenCode Markdown come from the same parser in
`scripts/plugin_agents.py`.

`--uninstall` updates the same file. Removing the whole saved selection (every
saved target and category) deletes it, so a later `--update` exits 4. Removing
whole targets (all saved categories for them) or whole categories (for every
saved target) rewrites it without them; component flags such as
`--instructions` on that run also drop the component when no saved target is
left out. `--uninstall --dry-run` prints `would delete` or `would rewrite` for
the state file instead. One selection cannot express a category or `--env`
removed from only some saved targets, so then the file stays unchanged, a note
goes to stderr, and `--update` reinstalls what was removed.

## What gets linked where

| Target | Skills | Command skills (`activation: command`) |
|---|---|---|
| `claude` | nothing; use the plugins | nothing; use the plugins |
| `codex` | `~/.agents/skills/<skill>` | `~/.agents/skills/<skill>` (see below) |
| `opencode` | `~/.config/opencode/skills/<skill>` | `~/.config/opencode/skills/<skill>` (see below) |

**OpenCode command skills.** A command skill stays in its ordinary skills
directory. Its `metadata` sets `opencode/slash: "true"` to expose `/name` in
the TUI and `opencode/autoinvoke: "false"` to keep it out of automatic
selection; `scripts/quick_validate.py` requires both on every
`activation: command` skill. The installer no longer creates command files, and
removes the `~/.config/opencode/command/<name>.md` links earlier versions made.

opencode also reads `~/.agents/skills/`, and it expects skill names to be
unique across all its roots
([opencode skills](https://opencode.ai/docs/skills)). So when codex already has
our link to a skill, opencode gets no link of its own for it, and the installer
removes one an earlier run created. Run order does not matter. opencode still
links a skill itself when codex lacks it: the skill's `targets` field excludes
codex, or codex was installed with a narrower `--env` or `--category`. After
`--uninstall` of codex alone, re-run `--target=opencode` so opencode gets its
own links back; the uninstall prints a reminder. opencode reads
`~/.claude/skills/` as well, but `install.sh` no longer links there; when the
Claude migration removes an old link, an installed opencode gets its own link
to that skill in its place.

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
./install.sh --target=opencode --category=architecture
./install.sh --target=codex    --category=refactoring,workflow
```

**By environment.** Each skill is tagged `environments: coding`, `chat`, or
both, so a chat app gets the chat skills and a coding agent the coding ones. A
skill without the field belongs to every environment.

```sh
./install.sh --target=opencode --env=coding
./install.sh --target=codex    --env=chat
```

Neither filter applies to Claude: there you choose a subset by installing only
some plugins, one per category. The plugins have no coding/chat split. Passing
`--env` or `--category` with `--target=claude` prints a warning that the filter
does not apply to Claude. With `--target=all`, the same warning appears for
Claude while the filters still select the Codex and opencode skills.

**Skills that skip an agent.** A skill can opt out of individual agents with a
`targets` field (a comma-separated subset of `claude`, `codex`, `opencode`;
absent means all of them). `install.sh` never links it for an excluded agent
and removes a link it created there before — use it when a runtime already
ships an equivalent of its own. Because `plugins/` is the Claude distribution
of these skills, a skill that excludes `claude` also gets no plugin symlink.

## Shared instructions (`--instructions`)

Skills are capabilities an agent loads on demand; shared rules use three
tiers in `instructions/`, ordered by numeric filename prefix:

- **Always on:** 20, 25, 50, 55 and 60.
- **Path-scoped in Claude:** 30 for Python files and 40 for R files. Codex and
  opencode get a pointer for the Python baseline and keep the R rules inline.
- **On demand:** 70, 80 and 85. Their pointers stay in the global instruction
  file, and `install.sh` places their full text under `~/.agents/instructions/`.
  In this repository, 70 and 85 are sourced from `instructions/on-demand/`; 80
  is sourced from `skills/llm-application-engineering/references/agent-pipelines.md`.

```sh
./install.sh --target=all --instructions             # sync rules, payloads and Claude's uv-init hook
./install.sh --target=all --instructions --dry-run   # preview
./install.sh --target=all --instructions --uninstall # strip the block
```

Always-on fragments and pointers are composed into a marker-delimited managed
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
reads a matching file. Codex and opencode have no equivalent: they use a
pointer to `~/.agents/instructions/30-python.md` for Python work and keep the
R fragment inline. Rule files without the `managed-by:` line are never touched.
The catch: nothing loads before the first matching read, so a rule that must
hold while *creating* the first such file does not belong behind `paths:`.
For the Python baseline, a Claude `Bash(uv init*)` PreToolUse hook reads the
installed `~/.agents/instructions/30-python.md` and adds it to context before
the first Python file exists.

Uninstall removes the selected global blocks and, when Claude is selected, its
uv-init hook. It removes an on-demand file
only when no remaining managed instruction block refers to it; a file at a
payload path without the ownership marker is never touched, and its pointer is
then left out of the block.

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

The flag is opt-in. For Codex and opencode, a plain `./install.sh --target=...`
writes skill links plus the generated subagent files and, for Codex, the
managed `skills.config` block; `--instructions` is the opt-in for the shared
rules. Claude plugins cannot ship `CLAUDE.md` content or path-scoped rules, so
`--instructions` installs the instruction blocks, path rules, on-demand files,
and Python `uv init` hook for Claude.

## PR merge guard (`--merge-guard`)

Coding agents act under your GitHub account, so branch protection and required
approvals do not stop them from merging their own pull requests. In this repo
that led to 22 PRs merged on red CI and 30 reverted merges (#557). The merge
guard is a model-free pre-tool hook: before each shell or MCP tool call it runs
[`scripts/pr_merge_guard.py`](../scripts/pr_merge_guard.py), which blocks the
call and tells the agent to ask you to merge.

```sh
./install.sh --target=all --merge-guard             # Codex and opencode
./install.sh --target=all --merge-guard --dry-run   # preview
./install.sh --target=all --merge-guard --uninstall # remove it again
claude plugin install merge-guard@fabiandistler-agents  # Claude Code
```

It blocks `gh pr merge` (including `--auto`), `gh api` or `curl` writes to
`repos/<o>/<r>/pulls/<n>/merge` and `repos/<o>/<r>/merges`, the GraphQL
mutations `mergePullRequest`, `enablePullRequestAutoMerge` and
`enqueuePullRequest`, and MCP tools named `merge_pull_request` or
`enable_pr_auto_merge`. GitHub has no REST endpoint for auto-merge. Reads pass:
`gh pr view`, `gh pr checks`, a local `git merge`. To merge, use the GitHub web
UI or your own terminal. The guard only checks the agent's tool calls.

| Agent | What gets installed | Hook |
|---|---|---|
| `claude` | the `merge-guard` plugin: `hooks/hooks.json` runs `scripts/pr_merge_guard.py`, which the plugin ships as a symlink to the repository's script; `install.sh --merge-guard` only prints the install command | [PreToolUse](https://code.claude.com/docs/en/hooks), exit 2 blocks |
| `codex` | a managed `[[hooks.PreToolUse]]` block in `~/.codex/config.toml` | [PreToolUse](https://developers.openai.com/codex/hooks), exit 2 blocks |
| `opencode` | symlink `~/.config/opencode/plugins/pr-merge-guard.js` | [`tool.execute.before`](https://opencode.ai/docs/plugins/) (1.x) and `ctx.tool.hook("execute.before")` ([2.x](https://opencode.ai/v2/docs/build/plugins)); a throw blocks |

All other settings, hooks and config stay as they are. The hook needs
`python3` on `PATH` when it runs. For Codex and opencode the hook command
points into this clone, so do not move the clone after installing. The Claude
plugin ships the guard script as a symlink to the repository's copy; Claude
dereferences it into its plugin cache, while a marketplace added from a local
clone resolves it in place.

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

## Secret read guard (`--secret-guard`)

Whatever a tool call prints lands in the agent's context and session log, so
one `cat .env` hands every secret in it to the model. The secret read guard is
a second model-free pre-tool hook, installed exactly like the merge guard:
[`scripts/secret_read_guard.py`](../scripts/secret_read_guard.py) blocks the
call and tells the agent to ask you to run the command or to provide a
sanitized value.

```sh
./install.sh --target=all --secret-guard             # Codex and opencode
./install.sh --target=all --secret-guard --uninstall # remove it again
claude plugin install secret-guard@fabiandistler-agents  # Claude Code
```

It blocks reading these files through a shell command or a file tool (Claude
`Read`, `Edit`, `Grep`; opencode `read`, `edit`, `grep`; MCP tools with a
`path`): `.env` and `.env.*` (but not `.env.example`, `.env.sample`,
`.env.template`), `.Renviron`, `.git-credentials`, `.netrc`, `.npmrc`,
`.pypirc`, `.envrc`, `.aws/credentials`, `.docker/config.json`,
`.kube/config` (also as `--kubeconfig`), `gh/hosts.yml`, private SSH keys
(`.ssh/id_*` without `.pub`), `~/.claude.json`, `.claude/.credentials.json`,
`.codex/auth.json`, opencode's `auth.json` and `mcp-auth.json`, the `pass`
store, gpg secret keys. Globs count (`cat ~/.ssh/*`). Some of these files often
hold no secret (a registry-only `.npmrc`); they are blocked anyway, because an
over-block costs one question and a leaked token a rotation. It also blocks
environment dumps: bare `env`, `printenv` without a name or with a secret-looking
one (`*_TOKEN`, `*_KEY`, `*SECRET*`, ...), `export -p`, `declare -x`/`-p`, bare
`set`, `/proc/<pid>/environ`, plus `pass show`, `gopass show`, `sops -d` and
`gpg --decrypt`.

It lets through what only names, writes or consumes a secret file: `ls`, `rm`,
`test -f`, `git add`/`rm`/`check-ignore`, `source .env`, `--env-file .env`,
`cp .env.example .env`, `ssh -i ~/.ssh/id_ed25519`; `env FOO=bar cmd` (the
command is checked) and `printenv PATH`. Listing file names (`Glob`, `ls`)
passes too. Malformed hook input fails open (exit 3), as with the merge guard.

The table above applies with `secret-guard`, `secret-read-guard.js` and the
`secret read guard` markers. Limits: it keeps secrets out of the context by
accident, it does not sandbox a determined agent. `echo $TOKEN`, a script or
`python -c` that opens `.env`, or `grep -r TOKEN .` get through.

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
Sandbox is inherited from your Codex session. Codex supports `model` and
`model_reasoning_effort` on custom agents, but the installer does not map
Claude's `model:` value into the generated TOML; add one there if you want it.
Claude's `tools:` allowlist has no direct Codex equivalent, so Codex agents
inherit their tools and permissions.

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

## Claude Code: plugins only

The repo doubles as a Claude plugin marketplace: every category is packaged as
one plugin, plus the hook-only `merge-guard` and `secret-guard` plugins (see
`plugins/` and
[`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json)), so
you can install exactly the domains you want. Plugin skills are namespaced
(`communication:documentation`); a routed category registers only its router,
so there it is the router that carries the namespace
(`architecture:architecture`). Command skills are namespaced too:
`/tldr` becomes `/communication:tldr`.

```sh
claude plugin marketplace add fabiandistler/agents
claude plugin install architecture@fabiandistler-agents
claude plugin install merge-guard@fabiandistler-agents
claude plugin install secret-guard@fabiandistler-agents
```

For Claude, skills, commands, subagents, and merge/secret guard hooks come from
plugins (#567). `--target=claude` syncs only shared instructions, path rules,
the Python `uv init` context hook, and cleanup of old links. Plugins cannot ship
`CLAUDE.md` content or path-scoped rules. Every `--target=claude` run, install
or `--uninstall`, also removes what earlier versions created, so skills do not
load twice next to the plugins:

- our symlinks in `~/.claude/skills` and `~/.claude/commands` (only links into
  this clone's `skills/`; foreign links stay);
- the merge-guard `PreToolUse` entry in `~/.claude/settings.json` (found by the
  script name in its command; every other setting stays). Install the
  `merge-guard` plugin to keep the guard.

With `--instructions`, the installer also adds a separate `PreToolUse` handler
to `~/.claude/settings.json` with `if: Bash(uv init*)`. It invokes the installed
`~/.agents/instructions/python_init_context.py`, which injects the Python
baseline. `--uninstall --instructions` removes only that handler.

**Updates.** Claude Code turns auto-update off by default for third-party
marketplaces such as this one. Turn it on in `/plugin` under Marketplaces, or
set `"autoUpdate": true` on the marketplace's `extraKnownMarketplaces` entry
in `settings.json`
([plugin loading](https://code.claude.com/docs/en/plugins/loading)).
Otherwise update by hand with
`claude plugin update <plugin>@fabiandistler-agents`. A marketplace added from
a local clone loads its plugins in place, so a `git pull` is enough there.

## Uninstall

`./install.sh --target=... --uninstall` removes the selected target's managed
artifacts: skill links, generated agent files, managed config and instruction
blocks, guard hooks, and its saved-state entry. Add `--dry-run` to preview.
When the whole saved selection is removed, the state file is deleted, so a
later `--update` exits 4. `--uninstall --instructions` also prunes on-demand
payload files that no remaining managed block refers to. Files this installer
does not own are never touched.

Claude plugins are outside this mechanism: `--uninstall` does not remove them,
because Claude owns the marketplace copy (a cache for a GitHub marketplace, or
the clone for a local one). Remove them in Claude Code instead:

```sh
claude plugin uninstall architecture@fabiandistler-agents
claude plugin marketplace remove fabiandistler-agents
```

## Maintainer notes

The Claude cloud-session mirror, the vendored skills, and the regeneration
order are maintainer material, not part of the user install path:
[install internals](maintainers/install-internals.md).
