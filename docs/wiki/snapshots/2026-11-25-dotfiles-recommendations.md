# 2026-11-25 dotfiles recommendations

Chief-of-staff session on 2026-11-25. The user asked for new dotfiles, features and tweaks.
Two subagent reports are the sources (scratchpad, not copied in): an inventory as of
`fabiandistler/dotfiles@5472b91` and a web research note. The research agent hit the shared
5-hour limit before it finished (see [shared usage limit](../problems/shared-usage-limit.md)).
Firecrawl credits ran out during that run.

## Findings as of `fabiandistler/dotfiles@5472b91`

- On `work`, `.bashrc`, `.bash_profile` and `.profile` are unmanaged (`.chezmoiignore:12-23`), so
  `RIPGREP_CONFIG_PATH`, EDITOR, fzf and the completion cache never reach Workbench. The deployed `~/.ripgreprc` has no effect there.
- Login shells: `dot_profile:12-32` sources `.bashrc` before `~/.local/bin` and `~/.cargo/env` are on PATH.
  This was inferred from the code and not run.
- fzf preview calls `bat`, but on Ubuntu `bat` is only an interactive alias of `batcat` (`dot_bashrc:34,175`).
- `dot_bashrc:133-141`: the alias-finder and bash-preexec order contradicts its own comments.
- Unguarded PATH prepends and hard-coded `/home/fabian` paths (`dot_bashrc:119,149,199-202`, `dot_npmrc:2`).
- No bootstrap: no `run_onchange_` scripts and no tool list. Only gitleaks comes from `.chezmoiexternal.toml`.
- `secrets.env` is sourced in plain text into every shell, so agent processes inherit it too (`dot_bashrc:144`).
- `chezmoi add` autoPush skips the gitleaks gate (`README.md:34`).
- The last 30 PRs went to sync robustness and the factory, almost none to new tool configs.

## Research (versions read 2026-11-25)

chezmoi v2.74.2 has builtin age and password-manager templates. These tools install without root:
zoxide 0.10.0, starship 1.27.0, direnv 2.38.2, delta 0.22.0 (inside the 7-day cooldown on 2026-11-25),
atuin 18.25.1 (NFS SQLite risk on Workbench, unverified), lazygit 0.66.3, eza 0.23.5, and air 0.13.0 and radian 0.8.0 via uv.
Claude Code 2.1.332 offers personal `permissions.deny` for secrets, statusline `prompt_cache` fields,
hooks such as a PostToolUse formatter and a Notification bell, and `enabledPlugins` in user settings.
The sandbox needs bubblewrap, which is unverified on Workbench.
Git gaps: `rebase.autoSquash`, `fetch.pruneTags`, `fetch.all` (>= 2.44), `diff.mnemonicPrefix`, `column.ui`.
Unverified items: the Workbench git version, NFS home, bwrap, rig stable version, and `.Rprofile` options (taken from memory).

## Status

On 2026-11-25 the recommendations went to the user, who had not decided. No issues were filed. *Superseded* later the same day:

Later on 2026-11-25 the user approved sections 1 and 2 plus delta, zoxide and direnv. A subagent filed dotfiles#85–#100 (excluding #89, #95 and #99, which are PRs):
- ready-for-agent: #85 common.sh, #86 login PATH, #88 fzf/bat, #90 PATH guards, #91 preexec order, #93 Claude deny for secrets, #97 zoxide, #98 direnv.
- ready-for-human: #87, #92 LC_ALL, #94 chezmoi add without gitleaks, #96 age vs. password manager.
  #87 is new: the workflows (`ci.yml:31-32`, `implementer.yml:73-74`, `rework.yml:71-72`) read every `.chezmoiexternal.toml` entry as the gitleaks pin, so a second external breaks CI.
  It blocks #97, #98 and #100.
- #100 delta: needs-triage. Add ready-for-agent on or after 2026-11-30 (cooldown).
- The implementer opened PRs #89 (#85), #95 (#86) and #99 (#93) right away.
- Verified in a scratch HOME: W1 and W5. Not verified: asset names and sha256 of the externals, the Claude `Read(~/...)` rule syntax, and whether chezmoi autoCommit runs hooks.
