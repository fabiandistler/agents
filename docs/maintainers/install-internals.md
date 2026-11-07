# Install internals: Claude cloud sessions

Maintainer material behind [`docs/install.md`](../install.md). It covers what
this repository commits for Claude Code cloud sessions inside it, which parts
are generated, and how to refresh them. The user install path does not need
this page.

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
| `.claude/settings.json` `PreToolUse` entries | the PR merge guard (`scripts/pr_merge_guard.py`) and the Python `Bash(uv init*)` context hook (`scripts/python_init_context.py`); the rest of the file is hand-written | `scripts/build_project_claude.py` |
| `.claude/hooks/session-start.sh` | SessionStart hook (cloud only): installs the pinned check tools into a venv put first on `PATH`, fetches Go via `proxy.golang.org` for the gitleaks hook (the proxy blocks `go.dev`), runs `prek install` and `prek install-hooks` | by hand |

## Regenerating the mirror

After changing a skill's frontmatter or an instruction fragment, the prek
commit hooks regenerate the manifest, the router member tables, and `.claude/`
(stage the result and commit again). Without the hooks, run the three
generators in this order:

```sh
python3 scripts/build_manifest.py
python3 scripts/build_routers.py
python3 scripts/build_project_claude.py
```

CI fails on drift (`--check`). The conventions behind those steps are in
[`docs/skill-conventions.md`](../skill-conventions.md); the contributor checklist is
[`docs/contributing.md`](../contributing.md).

Refresh the vendored skills with
`python3 scripts/vendor_mattpocock_skills.py` (optionally `--ref <sha>`).
Upstream skills named in the script's `EXCLUDED` set are never vendored:
`improve-codebase-architecture` is left out because this catalogue forks it
as `improve-codebase` (#492), so cloud sessions offer one such command, not two.
`ask-matt` is left out because it was deleted by hand on 2026-10-13, and a re-run
would bring it back. Pocock's `pr` is vendored again since 2026-10-20 at the
user's request; the catalogue itself still ships no PR-description skill
([`.out-of-scope/pr-description-skill.md`](../../.out-of-scope/pr-description-skill.md)).
`chief-of-staff` is still in upstream's `in-progress/` and is vendored anyway
(`INCLUDED_IN_PROGRESS`): it runs the long-lived goal sessions recorded in the
[wiki](../wiki/index.md).

Locally the same project skills would duplicate the marketplace plugins, so
`.claude/settings.json` switches this repo's plugins (and `mattpocock-skills`)
off for sessions inside this repo only. The vendored `code-review` shadows
Claude Code's built-in skill of that name in this repo.
