# Installing

Per-agent detail behind `install.sh`. The [README](../README.md) covers the
two normal paths; this page answers *what exactly did it write, and how do I
undo it* — read it when an install touched a config file you maintain by hand,
or when you want a subset of the catalogue.

## Contents

- [Verify the install](install-operations.md#verify-the-install) and [Troubleshooting](install-operations.md#troubleshooting)
- [Exit codes](install-operations.md#exit-codes)
- [Check](install-operations.md#check-the-managed-installation), [replay](install-operations.md#replay-the-last-install) and [update](install-operations.md#update-after-a-merge-or-rebase)
- [Detect installed agents](#detect-installed-agents)
- [OpenCode subagents](#opencode-subagents)
- [What gets linked where](#what-gets-linked-where)
- [Selecting a subset](#selecting-a-subset)
- [Shared instructions](install-optional-components.md#shared-instructions---instructions)
- [PR merge guard](install-optional-components.md#pr-merge-guard---merge-guard) and [secret read guard](install-optional-components.md#secret-read-guard---secret-guard)
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

How to confirm each agent loaded the install: [Checking and updating an install](install-operations.md#verify-the-install).

## Troubleshooting

Symptoms and where to look: [Troubleshooting](install-operations.md#troubleshooting).

## Exit codes

What each exit code from `install.sh` means: [Exit codes](install-operations.md#exit-codes).

## Check the managed installation

`--check` reports drift in the managed files without changing them: [Check the managed installation](install-operations.md#check-the-managed-installation).

## Replay the last install

`--update` replays the saved install: [Replay the last install](install-operations.md#replay-the-last-install).

## Update after a merge or rebase

`--git-hook` re-runs `--update` after a merge or rebase when the install drifted: [Update after a merge or rebase](install-operations.md#update-after-a-merge-or-rebase).

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

`--instructions` composes the shared rules in `instructions/` into each agent's global instruction file: [Shared instructions](install-optional-components.md#shared-instructions---instructions).

## PR merge guard (`--merge-guard`)

`--merge-guard` adds a model-free hook that stops agents from merging pull requests: [PR merge guard](install-optional-components.md#pr-merge-guard---merge-guard).

## Secret read guard (`--secret-guard`)

`--secret-guard` adds a model-free hook that stops agents from reading credential files or dumping the environment: [Secret read guard](install-optional-components.md#secret-read-guard---secret-guard).

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
the Python `uv init` context hook, the guard plugins, and cleanup of old links.

With `--merge-guard` or `--secret-guard`, `install.sh` installs the
`merge-guard` or `secret-guard` plugin in user scope with the `claude` CLI and
first adds the marketplace if Claude does not know it yet. It leaves a plugin
you disabled in `/plugin` disabled and warns instead, and `--check` reports
it as `missing`. Without the `claude` CLI on `PATH`, it warns and prints the
`claude plugin install` command. `--uninstall` with the same guard flag runs
`claude plugin uninstall`. It does not update a plugin Claude already has;
run `claude plugin marketplace update fabiandistler-agents` for that. Plugins cannot ship
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
