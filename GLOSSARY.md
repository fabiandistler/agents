# Context

Glossary for this repo. Terms here are the canonical vocabulary; skills and
issues should use them rather than synonyms.

## Install surface

An agent runtime this repo delivers skills to. There are three: `claude`
(Claude Code), `codex` (Codex CLI), `opencode`. A surface is *supported* when
the repo promises its skills reach that runtime — independent of how they get
there.

Not a synonym for "target". `--target=` is one installer's flag; the surface
exists whether or not that installer does.

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
