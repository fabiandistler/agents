# Installing

How each agent gets this repo's skills, and what `install.sh` writes on top.
The [README](../README.md) has the short version; this page answers *what
exactly did it write, and how do I undo it* — read it when an install touched
a config file you maintain by hand, or when you are setting up a new machine.

Everything `install.sh` does is reversible with the same command plus
`--uninstall`, and every command accepts `--dry-run`.

## One channel per surface

Skills reach each agent through exactly one channel, chosen for how it
refreshes ([ADR-0004](adr/0004-distribution-channels-per-surface.md)).
`install.sh` links no skills, for any agent.

| Surface | Skills come from | Refresh |
|---|---|---|
| Claude Code | marketplace plugin | automatic |
| Codex CLI | marketplace plugin, git source | `codex plugin marketplace upgrade` |
| opencode | skill path pointing at a clone | `git pull` |

Running two channels on one surface registers every skill twice — that is
the fault [#159](https://github.com/fabiandistler/agents/issues/159) reported
for Claude, and the reason the installer's symlink channel was retired.

**Claude Code** (also claude.ai, Claude Desktop, Cowork):

```
/plugin marketplace add fabiandistler/agents
/plugin install architecture@fabiandistler-agents
```

The marketplace auto-updates; no clone and no installer are needed for the
skills. Plugin skills are namespaced (`communication:documentation`); a routed
category registers only its router, so there it is the router that carries the
namespace (`architecture:architecture`).

**Codex CLI** reads the same
[`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json)
directly. Add the marketplace from its git URL — not from a local path, so the
clone is not load-bearing for this surface — then install the plugins you want:

```sh
codex plugin marketplace add https://github.com/fabiandistler/agents.git
codex plugin list                       # shows the six plugins from the git clone
codex plugin marketplace upgrade        # refresh the snapshot; Codex never does this on its own
```

If you added the marketplace from a local path before, remove that entry
(`codex plugin marketplace remove fabiandistler-agents`) and re-add it from the
URL, or the two sources compete.

**opencode** has no plugin format that carries skills, so it gets a skill path
pointing at a clone. Clone the repo, then add the path to your opencode config.
The key depends on the opencode version: 1.x (measured on 1.18.30 in ADR-0004)
reads `skills.paths`; the current v2 docs read a top-level `skills` array.
Check which one your version's schema (`https://opencode.ai/config.json`)
accepts:

```json
{ "skills": { "paths": ["~/src/agents/skills"] } }
```

```json
{ "skills": ["~/src/agents/skills"] }
```

(1.x first, v2 second.)

Two things to know: opencode reads `~/.claude/skills` too, so an old symlink
there registers a skill twice (the installer removes ours — see below); and
v2 discovers `SKILL.md` at any depth, so under it a router's `members/`
register individually rather than staying hidden behind the router. A
`git pull` in the clone is the refresh.

**Refresh on Codex and opencode is manual by design.** ADR-0004 puts the two
commands (`codex plugin marketplace upgrade`, `git pull` in the clone) on a
systemd user timer per machine rather than in this repo.

## What `install.sh` writes

The installer keeps exactly the jobs no plugin format can perform:

| Target | Writes |
|---|---|
| `claude` | managed instruction block in `~/.claude/CLAUDE.md` |
| `codex` | managed instruction block in `~/.codex/AGENTS.md`; routed-member block in `~/.codex/config.toml`; subagents in `~/.codex/agents/` |
| `opencode` | nothing — it reads `~/.claude/CLAUDE.md` (see below) |

```sh
./install.sh --target=all              # every target
./install.sh --target=all --dry-run    # preview
./install.sh --target=all --uninstall  # strip everything it wrote
```

On every run — install or uninstall — it also removes the skill symlinks an
earlier version created under each target's skill and command directories
(`~/.claude/skills`, `~/.claude/commands`, `~/.codex/skills`, `~/.codex/prompts`,
`~/.config/opencode/skills`, `~/.config/opencode/command`,
`~/.config/opencode/agent`). Only a symlink pointing into this clone's `skills/`
is removed, whether it still resolves or not; symlinks pointing anywhere else,
and real directories, are never touched. Upgrading past the symlink era is one
`./install.sh --target=all` per machine.

### Shared instructions

Skills are capabilities an agent loads on demand; the rules that should apply
to *every* session are something else. Those live in `instructions/` as
single-topic Markdown fragments, ordered by their numeric filename prefix.

Each fragment is authored once and composed into a marker-delimited managed
block in the agent's global instruction file — `~/.claude/CLAUDE.md` for Claude
Code, `~/.codex/AGENTS.md` for Codex CLI. The filenames differ because that is
what each agent reads; the content is one AGENTS.md-style document either way.
A fragment may limit itself to some agents with a `targets:` frontmatter field.

Anything outside the markers is left alone, so hand-written notes and
`@`-imports survive install, reinstall, and uninstall. Unbalanced markers (from
a hand edit) make the installer skip the file rather than guess.

opencode gets no file of its own on purpose: its instruction loader already
reads `~/.claude/CLAUDE.md` unless `disableClaudeCodePrompt` is set, so a
second copy would load every rule twice per session. That makes
`./install.sh --target=claude` the way opencode receives the rules.

### Codex CLI specifics

`--target=codex` needs `python3` for the subagents (skipped with a warning
otherwise). `--category=<name>[,<name>...]` selects which plugins' extras are
written; it is rejected for targets other than `codex` and `all`, where it
would select nothing.

**Subagents.** A Codex plugin cannot ship subagents, so the installer converts
each selected plugin's subagents (`coupling-analyst`, `cohesion-analyst`) into
[Codex custom agents](https://developers.openai.com/codex/subagents) under
`~/.codex/agents/<name>.toml`. The generated files carry a marker comment;
files you created yourself are never overwritten, and `--uninstall` removes
only marker-carrying files. Model and sandbox are inherited from your Codex
session — the Claude-specific `model:` and `tools:` fields have no Codex
equivalent.

**Router members.** Codex discovers skills recursively and follows symlinks
([openai/codex#22275](https://github.com/openai/codex/issues/22275)), so each
`members/<name>/SKILL.md` inside the plugin would otherwise register as its own
skill and the router's progressive disclosure would be lost. The installer
therefore disables every nested member by name in `~/.codex/config.toml`, via
a marker-delimited `[[skills.config]]` block (`enabled = false`). `--uninstall`
removes the block.

**Command skills.** Codex custom prompts are deprecated, so `activation:
command` skills arrive through the plugin as regular skills. Each carries an
`agents/openai.yaml` sidecar with `policy.allow_implicit_invocation: false`, so
Codex runs them only on an explicit `$skill-name`, never on its own.

**Legacy MCP cleanup.** Earlier versions registered a knowledge-base MCP server
per plugin. Those are gone — the skills' `references/` pages are read directly.
Both install and `--uninstall` strip whatever an older version left in
`~/.codex/config.toml` and remove its `~/.codex/agents-mcp-runtime` venv. Any
`[mcp_servers.*]` entries you added yourself are untouched.

Restart Codex to pick up new agents or config.

## Developing skills locally

Edits in the clone reach opencode immediately (its skill path *is* the clone)
and Codex after `codex plugin marketplace upgrade` once pushed. For Claude Code,
add the clone as a second, local marketplace only while working on a skill, and
remove it afterwards — with both the git and the local marketplace installed,
every skill appears twice.
