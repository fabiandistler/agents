# SKILL.md Format Reference

The authoritative frontmatter constraints for `SKILL.md`, per the Agent Skills format specification. For the directory layout (`scripts/`, `references/`, `assets/`) and the three-level progressive-disclosure loading model, see "Anatomy of a Skill" and "Progressive Disclosure" in `SKILL.md` — this file only adds the field-by-field constraints and where this repo is stricter than the general spec.

## Frontmatter fields

| Field | Required | Constraints |
|---|---|---|
| `name` | Yes | Max 64 characters. Lowercase letters, numbers, and hyphens only. Must not start or end with a hyphen, and must not contain consecutive hyphens (`--`). Must match the parent directory name. |
| `description` | Yes | Max 1024 characters, non-empty. Describes what the skill does and when to use it. |
| `license` | No | License name, or a reference to a bundled license file. |
| `compatibility` | No | Max 500 characters. Environment requirements (intended product, system packages, network access). Most skills don't need it. |
| `metadata` | No | Arbitrary string-to-string map for client-specific properties. |
| `allowed-tools` | No | Space-separated string of pre-approved tools. Experimental; support varies by agent implementation. |
| `argument-hint` | No | Placeholder text describing the arguments a user can pass when invoking the skill as a command (e.g. `"[yesterday \| today \| blockers]"`). Client-specific (Claude Code); ignored by agents that don't surface commands. |
| `disable-model-invocation` | No | Boolean. When `true`, the model won't auto-load the skill; it runs only when the user invokes it explicitly. Client-specific (Claude Code); ignored elsewhere. |

## Where this repo is stricter than the general spec

`AGENTS.md` and `scripts/build_manifest.py` narrow two of the fields above specifically for this repo:

- **`name` must equal the directory name.** The general spec states this too, but `build_manifest.py` doesn't enforce it programmatically — a mismatch produces a `skills.json` entry whose `path` and `name` silently disagree. Check it by eye when authoring or renaming a skill.
- **The first sentence of `description` becomes the `summary` field in `skills.json`** (`first_sentence()` in `build_manifest.py`, truncated at 200 characters with an ellipsis if longer). Write that first sentence as a self-contained what+when trigger — anything after it is invisible to tooling that only reads the manifest, not the full `SKILL.md`.

After editing any frontmatter, regenerate the manifest: `python3 scripts/build_manifest.py` (`--check` to verify it's in sync before committing).

## SKILL.md body length

Keep the body under ~500 lines; the general spec's own guidance is closer to 5000 tokens for the same section. If you're approaching the limit, move detail into `references/` and add a pointer from `SKILL.md` about when to follow up — see "Progressive Disclosure" above.
