# SKILL.md Format Reference

The authoritative frontmatter constraints for `SKILL.md`, per the Agent Skills format specification. For the directory layout (`scripts/`, `references/`, `assets/`) and the three-level progressive-disclosure loading model, see "Anatomy of a Skill" and "Progressive Disclosure" in `SKILL.md` — this file only adds the field-by-field constraints and where this repo is stricter than the general spec.

## Frontmatter fields

| Field | Required | Constraints |
|---|---|---|
| `name` | Yes | Max 64 characters. Lowercase letters, numbers, and hyphens only. Must not start or end with a hyphen, and must not contain consecutive hyphens (`--`). Must match the parent directory name. |
| `description` | Yes | Max 1024 characters per the spec, non-empty. Describes what the skill does and when to use it. Must not contain `<` — the description is interpolated into the agent's system prompt, where a `<` can open a tag that was never meant to exist. A bare `>` is fine (`Principle > System > Workflow`). **This repo budgets it much tighter — see below.** |
| `license` | No | License name, or a reference to a bundled license file. |
| `compatibility` | No | Max 500 characters. Environment requirements (intended product, system packages, network access). Most skills don't need it. |
| `metadata` | No | Arbitrary string-to-string map for client-specific properties. |
| `allowed-tools` | No | Space-separated string of pre-approved tools. Experimental; support varies by agent implementation. |
| `argument-hint` | No | Placeholder text describing the arguments a user can pass when invoking the skill as a command (e.g. `"[yesterday \| today \| blockers]"`). Client-specific (Claude Code); ignored by agents that don't surface commands. |
| `disable-model-invocation` | No | Boolean. When `true`, the model won't auto-load the skill; it runs only when the user invokes it explicitly. Client-specific (Claude Code); ignored elsewhere. Pair it with `activation: command` (below). |
| `category` | **Yes, in this repo** | One of `architecture`, `refactoring`, `ai-ml`, `workflow`, `communication`, `personal` (the fixed list in `build_manifest.py`). Repo-specific: `build_manifest.py` fails without it. Determines the catalogue section, the `install.sh --category` subset, and which plugin bundles the skill. |
| `activation` | No | `auto` (default), `command`, or `router`. Repo-specific field consumed by `build_manifest.py`, `build_routers.py` and `install.sh` — see below. |
| `environments` | No | Comma-separated list of `coding`, `chat` (e.g. `environments: coding, chat`); absent means every environment. Repo-specific: `install.sh --env` installs only the matching subset. |
| `targets` | No | Comma-separated subset of `claude`, `codex`, `opencode`; absent means all of them. Repo-specific field consumed by `build_manifest.py`, `install.sh`, and `check_plugins.py` — see below. |

## Where this repo is stricter than the general spec

`AGENTS.md` and `scripts/build_manifest.py` narrow two of the fields above specifically for this repo:

- **`name` must equal the directory name.** The general spec states this too, but `build_manifest.py` doesn't enforce it programmatically — a mismatch produces a `skills.json` entry whose `path` and `name` silently disagree. Check it by eye when authoring or renaming a skill.
- **The first sentence of `description` becomes the `summary` field in `skills.json`** (`first_sentence()` in `build_manifest.py`, truncated at 200 characters with an ellipsis if longer). Write that first sentence as a self-contained what+when trigger — anything after it is invisible to tooling that only reads the manifest, not the full `SKILL.md`.
- **Description budget (enforced by `scripts/check_descriptions.py`).** The description is always-loaded metadata competing for a tight context budget — Codex CLI truncates the skill list past ~2% of the context window — so this repo caps it well under the 1024-char spec limit: **≤250 characters** for most skills, **≤400** for the small high-traffic allowlist in `check_descriptions.py`. The aggregate across all `auto` skills is also capped. Put trigger lists and feature enumerations in the SKILL.md **body** (a leading `## When to use` section), not the frontmatter — progressive disclosure loads them only when the skill triggers. Keep the first sentence ≤200 chars so the `skills.json` summary isn't truncated.
- **`activation` controls how the skill is surfaced.** `auto` (default) skills are model-triggered; their description counts toward the auto-trigger budget. `command` skills are user-invoked only — for Claude and opencode `install.sh` links them into the target's command directory (`~/.claude/commands`, `~/.config/opencode/command`) as `<name>.md` instead of the skills directory, and `build_manifest.py` emits `"activation": "command"` in `skills.json`. Codex custom prompts are deprecated, so under codex a `command` skill installs into `~/.codex/skills/` like any skill; add an `agents/openai.yaml` sidecar with `policy.allow_implicit_invocation: false` so Codex only runs it on an explicit `$skill-name`. For Claude, also set `disable-model-invocation: true` (honored at runtime; other agents ignore it).

- **`activation: router` makes a skill its category's single entry point.** A router is named after its category (`name` must equal `category`) and is the only skill of that category registered at top level; the category's `auto` skills nest under the router's `members/` directory as symlinks and load lazily once the router routes to them, so the category costs one trigger entry instead of one per skill. Both the `members/` symlinks and the member table between the `<!-- BEGIN generated:members -->` / `<!-- END generated:members -->` markers in the router's body are generated by `scripts/build_routers.py` (run it after `build_manifest.py`; CI checks both for drift) — everything else in the router's `SKILL.md` is hand-authored. A router's description is the whole category's trigger surface, so `check_descriptions.py` grants it the wider budget and excludes it from the `auto` aggregate. Claude registers only top-level skills, so members stay hidden there; Codex discovers skills recursively and follows symlinks, so `install.sh --target=codex` additionally disables each nested member by name in `~/.codex/config.toml`.

- **`targets` restricts a skill to some agents.** Without the field a skill is installed for all of `claude`, `codex`, and `opencode`. With e.g. `targets: codex, opencode`, `install.sh` skips it under claude and removes a link it created there earlier, and `build_manifest.py` emits `"targets": ["codex", "opencode"]` in `skills.json`. Since `plugins/` is the Claude distribution, such a skill also carries no `plugins/<category>/skills/<name>` symlink. Reach for it when the runtime already has an equivalent built in — this repo's `skill-creator` opts out of claude because Claude Code ships its own.

After editing any frontmatter, regenerate the manifest: `python3 scripts/build_manifest.py` (`--check` to verify it's in sync before committing), and run `python3 scripts/check_descriptions.py`.

## SKILL.md body length

Keep the body under ~500 lines; the general spec's own guidance is closer to 5000 tokens for the same section. If you're approaching the limit, move detail into `references/` and add a pointer from `SKILL.md` about when to follow up — see "Progressive Disclosure" above.
