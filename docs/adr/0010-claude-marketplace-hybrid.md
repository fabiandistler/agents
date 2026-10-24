# ADR-0010: Claude gets plugins from the marketplace only; Codex and opencode keep `install.sh`

## Status

Accepted (2026-10-22). Supersedes ADR-0004 in part: its `claude` row stands,
its `codex` and `opencode` rows and "`install.sh` stops linking skills
entirely" do not.

Amended: the `secret-guard` plugin was added after this decision. It follows
the same split — `claude` gets it from the marketplace as a hook-only plugin,
`codex` and `opencode` get it from `install.sh --secret-guard`.

## Context

ADR-0004 gave each install surface one distribution channel and moved `claude`
and `codex` to the marketplace channel. The implementation was reverted five
days later (`4aedf98`, [#167](https://github.com/fabiandistler/agents/issues/167)):
Codex drops symlinks when it copies a plugin into its cache
([openai/codex#24770](https://github.com/openai/codex/issues/24770)), so every
plugin installed with an empty `skills/` tree. The revert put the symlink
channel back on all three surfaces, `claude` included, while ADR-0004 still
read as accepted. A Claude user with the marketplace installed therefore had
two channels on one surface again.

[#567](https://github.com/fabiandistler/agents/issues/567) asked which of the
installer's Claude jobs a plugin can take over. On 2026-10-21 it was tested
hands-on in throwaway `$HOME`s with Claude Code 2.1.306, Codex CLI 0.162.1 and
opencode 1.19.0:

- **Claude:** skills, routers with hidden members, command skills and both
  subagents install from the marketplace as the repo is; symlinks within the
  marketplace are dereferenced into the cache. The merge guard works as a
  plugin `hooks/hooks.json` PreToolUse hook and blocked `gh pr merge` in a
  headless run. No plugin component carries `CLAUDE.md` content or rules
  ([plugins-reference](https://code.claude.com/docs/en/plugins-reference)); a
  SessionStart hook can inject the fragments, but only under a 10,000-char cap
  per hook output. Auto-update is off by default for third-party marketplaces
  ([plugin loading](https://code.claude.com/docs/en/plugins/loading)).
- **Codex:** reads `.claude-plugin/marketplace.json`, but drops *every*
  symlink when it copies a plugin into its cache, even one inside the plugin.
  It has no subagent component and lists router members as top-level skills.
- **opencode:** has no marketplace; a JS package plugin could register
  everything, but `npm pack` drops symlinks too, so it needs a build step.

## Decision

Hybrid. On `claude`, everything a plugin can ship comes from the marketplace
only: skills, command skills, subagents, and the merge guard as the hook-only
`merge-guard` plugin. `install.sh --target=claude` keeps only the instruction
block and the path-scoped rules in `~/.claude/rules`, and on every run removes
what earlier versions created: our links in `~/.claude/skills` and
`~/.claude/commands` and the merge-guard entry in `~/.claude/settings.json`.

`codex` and `opencode` stay on the symlink channel through `install.sh`. The
cloud-session mirror (`scripts/build_project_claude.py`) is unaffected.

## Considered options

- **Hybrid (chosen).**
- **Claude fully plugin-only, instructions in a `core` plugin.** Rejected: the
  fragments must be split under the 10k cap and gated in CI, path-scoped rules
  need a per-session dedupe, and the failure direction flips: a broken rule
  frontmatter still loads, a broken hook drops every rule without a visible
  error. `~/.claude/rules` already does this natively.
- **ADR-0004 as written, Codex on the marketplace channel.** Rejected until
  Codex keeps symlinks or the repo ships real files under `plugins/`; even then
  the subagent TOMLs and the member-suppression managed block stay with the
  installer.
- **opencode as a package plugin.** Rejected for now: a publish step that
  dereferences symlinks, a v1/v2 dual export, and our code running at every
  opencode startup.
- **Keep linking Claude skills.** Rejected: next to the marketplace it
  registers every skill twice (`/tldr` and `/communication:tldr`), the fault
  ADR-0004 named.

## Consequences

- Claude command skills are namespaced: `/tldr` becomes `/communication:tldr`.
- `--env` and `--category` no longer shape what Claude gets; plugins split by
  category only.
- Refresh on `claude` is automatic only once the user enables auto-update:
  Claude Code turns it off by default for third-party marketplaces. ADR-0004
  measured a machine where it had been switched on. `docs/install.md` says so.
- opencode stops seeing our skills through its `~/.claude/skills`
  compatibility root, which removes a double load there.
- The plugin manifests carry no `version`, so every commit is a new version.
  Adding one would pin every user.

## Notes

Reopen the `codex` row when Codex keeps in-marketplace symlinks or the layout
puts real files under `plugins/`. Reopen the instructions question when a
plugin format can carry rules natively.
