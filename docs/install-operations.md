# Checking and updating an install

How to confirm an install worked, read its exit codes, find drift, and
keep it current after the checkout changes. The rest of the per-agent
detail is in [Installing](install.md).

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
| Skill missing in Claude Code | Is the marketplace added and the plugin installed? Check `/plugin`; see [Claude Code: plugins only](install.md#claude-code-plugins-only). |
| Codex skill missing | Check `~/.agents/skills/` and the legacy `~/.codex/skills/`; restart Codex; run `--update --check`. |
| The same skill appears twice | Codex and opencode share `~/.agents/skills/`; see [What gets linked where](install.md#what-gets-linked-where). |
| A guard hook does not fire | Codex skips an untrusted hook until you open `/hooks`; opencode does not run plugin hooks under `opencode run` or in the Desktop app. See the [guard sections](install-optional-components.md#pr-merge-guard---merge-guard). |
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
