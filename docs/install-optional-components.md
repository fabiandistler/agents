# Optional components: instructions and guards

The opt-in parts of an install that write into each agent's global
configuration instead of linking skills: `--instructions`, `--merge-guard`
and `--secret-guard`. The rest of the per-agent detail is in
[Installing](install.md).

## Shared instructions (`--instructions`)

Skills are capabilities an agent loads on demand; shared rules use three
tiers in `instructions/`, ordered by numeric filename prefix:

- **Always on:** 20, 25, 45, 50, 55 and 60.
- **Path-scoped in Claude:** 30 for Python files and 40 for R files. Codex and
  opencode get a pointer for the Python baseline and keep the R rules inline.
- **On demand:** 70, 80 and 85. Their pointers stay in the global instruction
  file, and `install.sh` places their full text under `~/.agents/instructions/`.
  In this repository, 70 and 85 are sourced from `instructions/on-demand/`; 80
  is sourced from `skills/llm-application-engineering/references/agent-pipelines.md`.

```sh
./install.sh --target=all --instructions             # sync rules, payloads and Claude's uv-init hook
./install.sh --target=all --instructions --dry-run   # preview
./install.sh --target=all --instructions --uninstall # strip the block
```

Always-on fragments and pointers are composed into a marker-delimited managed
block in the agent's global instruction file — `~/.claude/CLAUDE.md` for Claude
Code, `~/.codex/AGENTS.md` for Codex CLI, `~/.config/opencode/AGENTS.md` for
opencode. The filenames differ because that is
what each agent reads; the content is one AGENTS.md-style document either way.
A fragment may limit itself to some agents with a `targets:` frontmatter field,
exactly as a skill does.

A fragment with a `paths:` field (comma-separated globs, e.g.
`paths: **/*.R, **/DESCRIPTION`) leaves Claude's block and is written as a
[path-scoped rule](https://code.claude.com/docs/en/memory#path-specific-rules)
to `~/.claude/rules/agents-<fragment>.md`, which Claude Code loads only once it
reads a matching file. Codex and opencode have no equivalent: they use a
pointer to `~/.agents/instructions/30-python.md` for Python work and keep the
R fragment inline. Rule files without the `managed-by:` line are never touched.
The catch: nothing loads before the first matching read, so a rule that must
hold while *creating* the first such file does not belong behind `paths:`.
For the Python baseline, a Claude `Bash(uv init*)` PreToolUse hook reads the
installed `~/.agents/instructions/30-python.md` and adds it to context before
the first Python file exists.

Uninstall removes the selected global blocks and, when Claude is selected, its
uv-init hook. It removes an on-demand file
only when no remaining managed instruction block refers to it; a file at a
payload path without the ownership marker is never touched, and its pointer is
then left out of the block.

Anything outside the markers is left alone, so hand-written notes and
`@`-imports survive install, reinstall, and uninstall. Unbalanced markers (from
a hand edit) make the installer skip the file rather than guess.

opencode reads `~/.claude/CLAUDE.md` only as a fallback when
`~/.config/opencode/AGENTS.md` does not exist
([rules](https://opencode.ai/docs/rules)), and opencode V2 drops that fallback
([instructions](https://opencode.ai/v2/docs/instructions)), so it gets a file of
its own and no rule loads twice. Once that file exists, opencode stops reading
`~/.claude/CLAUDE.md`: anything you wrote there outside the markers and want in
opencode too belongs in `~/.config/opencode/AGENTS.md` as well.

The flag is opt-in. For Codex and opencode, a plain `./install.sh --target=...`
writes skill links plus the generated subagent files and, for Codex, the
managed `skills.config` block; `--instructions` is the opt-in for the shared
rules. Claude plugins cannot ship `CLAUDE.md` content or path-scoped rules, so
`--instructions` installs the instruction blocks, path rules, on-demand files,
and Python `uv init` hook for Claude.

## PR merge guard (`--merge-guard`)

Coding agents act under your GitHub account, so branch protection and required
approvals do not stop them from merging their own pull requests. In this repo
that led to 22 PRs merged on red CI and 30 reverted merges (#557). The merge
guard is a model-free pre-tool hook: before each shell or MCP tool call it runs
[`scripts/pr_merge_guard.py`](../scripts/pr_merge_guard.py), which blocks the
call and tells the agent to ask you to merge.

```sh
./install.sh --target=all --merge-guard             # Claude Code, Codex and opencode
./install.sh --target=all --merge-guard --dry-run   # preview
./install.sh --target=all --merge-guard --uninstall # remove it again
```

It blocks `gh pr merge` (including `--auto`), `gh api` or `curl` writes to
`repos/<o>/<r>/pulls/<n>/merge` and `repos/<o>/<r>/merges`, the GraphQL
mutations `mergePullRequest`, `enablePullRequestAutoMerge` and
`enqueuePullRequest`, and MCP tools named `merge_pull_request` or
`enable_pr_auto_merge`. GitHub has no REST endpoint for auto-merge. Reads pass:
`gh pr view`, `gh pr checks`, a local `git merge`. To merge, use the GitHub web
UI or your own terminal. The guard only checks the agent's tool calls.

| Agent | What gets installed | Hook |
|---|---|---|
| `claude` | the `merge-guard` plugin: `hooks/hooks.json` runs `scripts/pr_merge_guard.py`, which the plugin ships as a symlink to the repository's script; `install.sh --merge-guard` installs the plugin with the `claude` CLI (see [Claude Code: plugins only](install.md#claude-code-plugins-only)) | [PreToolUse](https://code.claude.com/docs/en/hooks), exit 2 blocks |
| `codex` | a managed `[[hooks.PreToolUse]]` block in `~/.codex/config.toml` | [PreToolUse](https://developers.openai.com/codex/hooks), exit 2 blocks |
| `opencode` | symlink `~/.config/opencode/plugins/pr-merge-guard.js` | [`tool.execute.before`](https://opencode.ai/docs/plugins/) (1.x) and `ctx.tool.hook("execute.before")` ([2.x](https://opencode.ai/v2/docs/build/plugins)); a throw blocks |

All other settings, hooks and config stay as they are. The hook needs
`python3` on `PATH` when it runs. For Codex and opencode the hook command
points into this clone, so do not move the clone after installing. The Claude
plugin ships the guard script as a symlink to the repository's copy; Claude
dereferences it into its plugin cache, while a marketplace added from a local
clone resolves it in place.

Limits:

- **Codex** runs a new or changed non-managed hook only after you trust it.
  Open `/hooks` once after installing. Until then Codex skips the guard and
  warns at startup.
- **opencode** does not fire plugin hooks under headless `opencode run`
  ([anomalyco/opencode#41422](https://github.com/anomalyco/opencode/issues/41422))
  or in the Desktop app
  ([anomalyco/opencode#38604](https://github.com/anomalyco/opencode/issues/38604)),
  and may skip them for MCP tools in experimental code mode. The plugin's default
  export with `server()` needs opencode 1.18.29 or later.
- Hooks are a guardrail, not a security boundary. A command the parser does not
  recognize (a `gh` alias, a script file that calls `gh pr merge`) gets
  through. A required status check on `main` is still the backstop.

## Secret read guard (`--secret-guard`)

Whatever a tool call prints lands in the agent's context and session log, so
one `cat .env` hands every secret in it to the model. The secret read guard is
a second model-free pre-tool hook, installed exactly like the merge guard:
[`scripts/secret_read_guard.py`](../scripts/secret_read_guard.py) blocks the
call and tells the agent to ask you to run the command or to provide a
sanitized value.

```sh
./install.sh --target=all --secret-guard             # Claude Code, Codex and opencode
./install.sh --target=all --secret-guard --uninstall # remove it again
```

It blocks reading these files through a shell command or a file tool (Claude
`Read`, `Edit`, `Grep`; opencode `read`, `edit`, `grep`; MCP tools with a
`path`): `.env`, `.env.*` and `*.env` (but not their `example`, `sample` and
`template` variants such as `.env.example` or `example.env`), `.Renviron`,
`.git-credentials`, `.netrc`, `.npmrc`, `.pypirc`, `.envrc`,
`.aws/credentials`, `.docker/config.json`, `.kube/config` (also as
`--kubeconfig`), `gh/hosts.yml`, `rclone/rclone.conf*`, private SSH keys
(`.ssh/id_*` without `.pub`), `~/.claude.json` and its copies
(`.claude.json.*`), `.claude/.credentials.json`, `.codex/auth.json`,
opencode's `auth.json` and `mcp-auth.json`, `.gemini/oauth_creds.json` and
`gemini-credentials.json`, `.azure/msal_token_cache.json` and
`msal_http_cache.bin`, `.kaggle/kaggle.json` and `access_token` (also under
`$XDG_CONFIG_HOME/kaggle`), `todoist-cli/config.json`, anything under
`.pyicloud*/`, the `pass` store, gpg secret keys. Globs in the file name count
(`cat ~/.ssh/*`, `cat ~/.config/*.env`). Some of these files often
hold no secret (a registry-only `.npmrc`); they are blocked anyway, because an
over-block costs one question and a leaked token a rotation. It also blocks
environment dumps: bare `env`, `printenv` without a name or with a secret-looking
one (`*_TOKEN`, `*_KEY`, `*SECRET*`, ...), `export -p`, `declare -x`/`-p`, bare
`set`, `/proc/<pid>/environ`, plus `pass show`, `gopass show`, `sops -d` and
`gpg --decrypt`.

It lets through what only names, writes or consumes a secret file: `ls`, `rm`,
`test -f`, `git add`/`rm`/`check-ignore`, `source .env`, `--env-file .env`,
`cp .env.example .env`, `ssh -i ~/.ssh/id_ed25519`; `env FOO=bar cmd` (the
command is checked) and `printenv PATH`. Listing file names (`Glob`, `ls`)
passes too. Malformed hook input fails open (exit 3), as with the merge guard.

The table above applies with `secret-guard`, `secret-read-guard.js` and the
`secret read guard` markers. Limits: it keeps secrets out of the context by
accident, it does not sandbox a determined agent. `echo $TOKEN`, a script or
`python -c` that opens `.env`, or `grep -r TOKEN .` get through. So do a bare
`cat *` next to a `secrets.env` and a glob in a directory name
(`cat ~/.config/*/rclone.conf`).
