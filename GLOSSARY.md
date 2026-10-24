# Glossary

Glossary for this repo. Terms here are the canonical vocabulary; skills and
issues should use them rather than synonyms.

## Skill

A directory under `skills/` whose `SKILL.md` carries frontmatter and a body an
agent reads when a request matches. It loads on demand; material it does not
need stays in `references/`.

Not a synonym for "plugin" (a delivery bundle) or "instruction" (a rule that
applies to every session).

## Auto skill

A skill with `activation: auto` (the default): the model sees its description
and loads it when the situation matches. Its description counts toward the
auto-trigger budget.

Not a synonym for "always on": an auto skill still loads only when triggered.

## Command skill

A skill with `activation: command`: the user invokes it, and the runtime keeps
it out of automatic selection. Claude Code exposes it as
`/<plugin>:<name>`, opencode as `/name`, Codex as `$name`.

Not a synonym for "router": a router is model-triggered and routes to members.

## Router

A skill named after its category with `activation: router`. It is the only
skill of its category registered at top level; its description covers the
whole category and its body routes to a member.

Not a synonym for "plugin": a plugin bundles skills for one runtime, a router
organizes them within the catalogue.

## Member

An auto skill nested under a router's `members/` directory. It is a normal
top-level skill directory, linked there by `scripts/build_routers.py`, and it
loads only when the router routes to it. Every skill with the router's
`category` and `activation: auto` becomes a member; command skills in that
category are not nested.

Not a separately registered skill: a member has no top-level trigger of its
own.

## Top-level skill

A skill directory directly under `skills/` that is not a router member. It is
the unit a plugin symlink and the installer's skill link point at.

Not a synonym for "auto skill": a command skill is top-level too, while a
router member is not.

## Plugin

A directory under `plugins/` with `.claude-plugin/plugin.json`, bundling one
category's skills for the Claude marketplace. Two hook-only plugins carry the
guards.

Not a synonym for "skill": the plugin is the delivery bundle, the skill is the
content.

## Marketplace

The Claude distribution channel: `.claude-plugin/marketplace.json` lists the
plugins, and a runtime adds the repository as a marketplace and installs
plugins from it. See also "distribution channel".

Not a synonym for "catalogue": the catalogue is what exists in `skills.json`;
the marketplace is how Claude receives a subset of it.

## Manifest (`skills.json`)

The generated index of every skill: `version` plus `skills[]` with `name`,
`category`, `path`, `summary`, `activation` (`auto` is omitted, being the
default), and optional `compatibility`, `version`, `environments` and
`targets`. For a normal skill the summary is the first sentence; for a router
it is the whole description with `when_to_use` appended. `scripts/build_manifest.py`
writes it; do not edit it by hand.

Not a synonym for the skills themselves: it is a summary index, not the
`SKILL.md` bodies.

## Install surface

An agent runtime this repo delivers skills to. There are three: `claude`
(Claude Code), `codex` (Codex CLI), `opencode`. A surface is *supported* when
the repo promises its skills reach that runtime — independent of how they get
there.

Not a synonym for "target". `--target=` is one installer's flag that selects
one or more surfaces; the surface exists whether or not that installer does.

## Forge

The git host that serves a project's remote and its pull requests: GitHub or
Azure DevOps. A skill that opens pull requests detects the forge from the
remote URL and uses its CLI.

Not the distribution channel (how skills reach a runtime) and not the install
surface (the runtime they reach).

## Loop runner

The agent CLI that executes a skill's autonomous loop headlessly, one fresh
context per task (`claude`, `codex`, or `opencode`). It is chosen per run and
need not match the install surface the skill was invoked from.

Not a synonym for "install surface" or "agent".

## Distribution channel

The mechanism carrying skills from this repo to an install surface. Two exist:
the **marketplace channel** (the runtime fetches and refreshes a plugin itself)
and the **symlink channel** (`install.sh` links a local clone into the
runtime's skill directory).

A surface is served by exactly one channel at a time. Two channels on one
surface register every skill twice.

## Refresh

How an installed skill reaches its newest version on a given surface. Refresh
is **automatic** when the runtime pulls on its own, and **manual** when a human
must run a command on every machine. The distinction, not the channel, is what
this repo optimises for.

## Instruction tier

One of the three layers in `instructions/`: always on, Claude path-scoped, and
on demand. The tier decides when a fragment enters an agent's context.

Not a synonym for a skill: a skill loads on a trigger, an instruction applies
to a session or a matching file.

## Managed block

A marker-delimited region that `install.sh` owns inside a file it does not:
the instruction block in an agent's global instruction file, or the
routed-member overrides in `~/.codex/config.toml`. The installer replaces or
removes only what lies between its markers. When the markers are unbalanced
(a hand edit), it leaves the whole file untouched.

## Instruction block

The managed block in an agent's global instruction file holding the
composed `instructions/` fragments. It is not a skill: skills load on demand,
an instruction block applies to every session. Content outside the markers is
never this repo's to touch.

## ADR

An Architecture Decision Record under `docs/adr/`: one decision, its context,
the rejected options, and the consequences. The index is
[`docs/adr/README.md`](docs/adr/README.md).

Not a synonym for a how-to page: an ADR records why, not how to operate the
result.

## Check / CI gate

A gate that CI runs through `scripts/check_all.sh`, each with a stable name
shown by `--list`. Most are scripts under `scripts/`; some wrap pytest, prek,
or the installer smoke test. A `MISSING` tool counts as not run, never as
green.

Not a synonym for a review: a check decides what a script can decide; the
weekly skill audit handles judgement.
