# SKILL.md Format Reference

The authoritative frontmatter constraints for `SKILL.md`, per the Agent Skills format specification. For the directory layout (`scripts/`, `references/`, `assets/`) and the three-level progressive-disclosure loading model, see "Anatomy of a Skill" and "Progressive Disclosure" in `SKILL.md` — this file only adds the field-by-field constraints and where this repo is stricter than the general spec.

## Frontmatter fields

| Field | Required | Constraints |
|---|---|---|
| `name` | Yes | Max 64 characters. Lowercase letters, numbers, and hyphens only. Must not start or end with a hyphen, and must not contain consecutive hyphens (`--`). Must match the parent directory name. |
| `description` | Yes | Max 1024 characters per the spec, non-empty. Describes what the skill does and when to use it. **This repo budgets it much tighter — see below.** |
| `license` | No | License name, or a reference to a bundled license file. |
| `compatibility` | No | Max 500 characters. Environment requirements (intended product, system packages, network access). Most skills don't need it. |
| `metadata` | No | Arbitrary string-to-string map for client-specific properties. |
| `allowed-tools` | No | Space-separated string of pre-approved tools. Experimental; support varies by agent implementation. |
| `argument-hint` | No | Placeholder text describing the arguments a user can pass when invoking the skill as a command (e.g. `"[yesterday \| today \| blockers]"`). Client-specific (Claude Code); ignored by agents that don't surface commands. |
| `disable-model-invocation` | No | Boolean. When `true`, the model won't auto-load the skill; it runs only when the user invokes it explicitly. Client-specific (Claude Code); ignored elsewhere. Pair it with `activation: command` (below). |
| `activation` | No | `auto` (default) or `command`. Repo-specific field consumed by `build_manifest.py` and `install.sh` — see below. |

## Where this repo is stricter than the general spec

`AGENTS.md` and `scripts/build_manifest.py` narrow two of the fields above specifically for this repo:

- **`name` must equal the directory name.** The general spec states this too, but `build_manifest.py` doesn't enforce it programmatically — a mismatch produces a `skills.json` entry whose `path` and `name` silently disagree. Check it by eye when authoring or renaming a skill.
- **The first sentence of `description` becomes the `summary` field in `skills.json`** (`first_sentence()` in `build_manifest.py`, truncated at 200 characters with an ellipsis if longer). Write that first sentence as a self-contained what+when trigger — anything after it is invisible to tooling that only reads the manifest, not the full `SKILL.md`.
- **Description budget (enforced by `scripts/check_descriptions.py`).** The description is always-loaded metadata competing for a tight context budget — Codex CLI truncates the skill list past ~2% of the context window — so this repo caps it well under the 1024-char spec limit: **≤250 characters** for most skills, **≤400** for the small high-traffic allowlist in `check_descriptions.py`. The aggregate across all `auto` skills is also capped. Put trigger lists and feature enumerations in the SKILL.md **body** (a leading `## When to use` section), not the frontmatter — progressive disclosure loads them only when the skill triggers. Keep the first sentence ≤200 chars so the `skills.json` summary isn't truncated.
- **`activation` controls how the skill is surfaced.** `auto` (default) skills are model-triggered; their description counts toward the auto-trigger budget. `command` skills are user-invoked only — `install.sh` links them into each target's command directory (`~/.claude/commands`, `~/.codex/prompts`, `~/.config/opencode/command`) as `<name>.md` instead of the skills directory, and `build_manifest.py` emits `"activation": "command"` in `skills.json`. For a `command` skill, also set `disable-model-invocation: true` (Claude honors it at runtime; other agents ignore it).

After editing any frontmatter, regenerate the manifest: `python3 scripts/build_manifest.py` (`--check` to verify it's in sync before committing), and run `python3 scripts/check_descriptions.py`.

## SKILL.md body length

Keep the body under ~500 lines; the general spec's own guidance is closer to 5000 tokens for the same section. If you're approaching the limit, move detail into `references/` and add a pointer from `SKILL.md` about when to follow up — see "Progressive Disclosure" above.
