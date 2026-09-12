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
| `codex` | `~/.codex/skills/<skill>` | `~/.codex/skills/<skill>` (see below) |
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
Code, `~/.codex/AGENTS.md` for Codex CLI. The filenames differ because that is
what each agent reads; the content is one AGENTS.md-style document either way.
A fragment may limit itself to some agents with a `targets:` frontmatter field,
exactly as a skill does.

Anything outside the markers is left alone, so hand-written notes and
`@`-imports survive install, reinstall, and uninstall. Unbalanced markers (from
a hand edit) make the installer skip the file rather than guess.

opencode gets no file of its own on purpose: its instruction loader already
reads `~/.claude/CLAUDE.md` unless `disableClaudeCodePrompt` is set, so a
second copy would load every rule twice per session.

The flag is opt-in — plain `./install.sh --target=...` only touches skills.

## Codex CLI specifics

For Codex, `--target=codex` covers the full plugins, not just the skills. It
needs `python3` (the extras are skipped with a warning otherwise); `--env`
filters skills only, while the extras follow `--category`.

**Subagents.** Each selected plugin's subagents (`coupling-analyst`,
`cohesion-analyst`) are converted into [Codex custom
agents](https://developers.openai.com/codex/subagents) under
`~/.codex/agents/<name>.toml`. The generated files carry a marker comment;
files you created yourself are never overwritten, and `--uninstall` removes
only marker-carrying files. Model and sandbox are inherited from your Codex
session — the Claude-specific `model:` and `tools:` fields have no Codex
equivalent.

**Router members.** Codex discovers skills recursively and follows symlinks
([openai/codex#22275](https://github.com/openai/codex/issues/22275)), so each
`members/<name>/SKILL.md` would otherwise register as its own skill and the
router's progressive disclosure would be lost. The installer therefore disables
every nested member by name in `~/.codex/config.toml`, via a marker-delimited
`[[skills.config]]` block (`enabled = false`). `--uninstall` removes the block.

**Command skills.** Codex custom prompts are deprecated, so `activation:
command` skills install as regular skills under `~/.codex/skills/`. Each
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
