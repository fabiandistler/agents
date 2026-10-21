# Installer automation for Codex CLI and opencode

Research note, 2026-10-21. Question: what does a Codex or opencode user still
do by hand with `install.sh`, and what can the installer take over? The
evidence is `install.sh`, `docs/install.md` and `scripts/test_install.sh` at
`d3af143`. Agent behaviour was checked against first-party docs, which are
cited inline. Proposals are written to comply with
`instructions/85-agent-scripts.md`.

## Contents

- [1. What is manual today](#1-what-is-manual-today)
- [2. Defects found on the way](#2-defects-found-on-the-way)
- [3. What can be automated](#3-what-can-be-automated)
- [4. Ranked proposals](#4-ranked-proposals)
- [5. Risks and constraints](#5-risks-and-constraints)
- [Sources](#sources)

## 1. What is manual today

**Flags to remember on every run.** `--target` is required: with no target the
script exits 2 (`install.sh:144`). Nothing records which flags the last run
used. `--env`, `--category`, `--instructions` and `--merge-guard` all have to
be typed again each time. If a re-run leaves out `--instructions`, the managed
block stays in place and silently goes stale. It is not refreshed, and it is
not removed.

**Re-runs after `git pull`.** The symlinked skill directories pick up new
content on their own. Everything else is a snapshot that only changes on a
re-run:

- new, renamed or deleted skills (links are only created and pruned during a run);
- Codex custom agents (`~/.codex/agents/*.toml`), which are copies of the agent bodies with `${CLAUDE_PLUGIN_ROOT}` already resolved;
- the Codex routed-member override block, which goes stale when a router gains a member;
- the instructions blocks in `CLAUDE.md` and `AGENTS.md`, and `~/.claude/rules/agents-*.md`.

No hook, verb or reminder tells the user that a re-run is due.

**Config edits the user still makes.** For Codex, a new or changed merge-guard
hook stays inactive until the user trusts it in `/hooks`
(`docs/install.md:134`). The user also has to restart Codex after any change to
`config.toml` or the agents. For opencode, the installer makes no config edits
at all.

**Claude/Codex-only today, missing for opencode.**

- **Subagents.** Claude loads `plugins/*/agents/*.md` natively, and Codex gets TOML conversions. opencode gets nothing, although it supports Markdown subagents in `~/.config/opencode/agents/` (with `description`, `mode: subagent` and `permission`) ([opencode agents](https://opencode.ai/docs/agents)).
- **Path-scoped rules.** These are Claude-only (`~/.claude/rules`). Codex and opencode get every fragment unconditionally. Neither has an equivalent, so this one is not a gap the installer can close.
- **Plugin marketplace install.** Claude has one. Codex now has one too (see §3), and the repo does not use it.

## 2. Defects found on the way

These surfaced during the audit. Fix them before adding automation, because
every automated re-run would trigger them.

1. **A narrower `--category` re-run strips the Codex member overrides.** It was reproduced in a temp `$HOME`. First `--target=codex`, then `--target=codex --category=communication`, prints `removed routed-member skill overrides`. The `architecture` and `ai-ml` router links are still in place, so all nine members register in Codex as top-level skills again. Cause: `codex_disabled_members` is built only from `list_skills`, which is filtered by category, and an empty list removes the block (`install.sh:521`). Test 18 covers only a fresh `$HOME`. This bites any `--update` that re-runs with a subset.
2. **Codex agent TOMLs are never pruned.** `uninstall_codex_agents` walks only the agents the repo ships now (`install.sh:660`). A renamed or deleted subagent leaves its marker file behind for good. Skills have `prune_stale_skill_links`, and agents have no equivalent.
3. **opencode loads every skill twice when claude and opencode are both installed.** opencode reads `~/.config/opencode/skills`, `~/.claude/skills` and `~/.agents/skills` ([opencode skills](https://opencode.ai/docs/skills); same list in [v2](https://opencode.ai/v2/docs/skills)), and it requires skill names to be unique across all locations. In a temp `$HOME`, `--target=claude` plus `--target=opencode` gave 10 links in each directory.
4. **Codex is linked into a deprecated directory.** The documented user scope is `$HOME/.agents/skills`. `$CODEX_HOME/skills` (`~/.codex/skills`) is kept "for backward compatibility" ([Codex skills](https://developers.openai.com/codex/skills); the source comment is quoted in [cli/cli#14153](https://github.com/cli/cli/issues/14153)).
5. **The opencode command directory name is out of date.** The docs name `~/.config/opencode/commands/` ([opencode commands](https://opencode.ai/docs/commands)). The installer writes to `command/` (singular). The 1.x loader still globs `{command,commands}`, but the docs no longer mention the singular form, so it could be dropped without notice.
6. **The member-disable key is undocumented.** `[[skills.config]] name = …` exists in Codex source (`codex-rs/core/src/config/edit.rs`), but the config reference documents only `path` ([config reference](https://learn.chatgpt.com/docs/config-file/config-reference)). `path` is the documented and stable selector.
7. **`--help` breaks the agent-script rules.** It prints 101 lines against a limit of about 25. Exit codes 1 and 2 exist but are not documented in it.

## 3. What can be automated

**Auto-detect targets.** Detection uses data, not prompts:

- claude: `command -v claude` or `~/.claude/`;
- codex: `command -v codex` or `~/.codex/`;
- opencode: `command -v opencode` or `~/.config/opencode/`.

Make this an explicit value, `--target=detected`, that prints the targets it
resolved. Do not make it the default. Under the named-writes rule, a bare
`./install.sh` must not write anything. Keep it exiting 2, and make the error
name `detected` as one of the allowed values.

**Remembered flags and an `--update` verb.** After each successful run, write
`{targets, env, category, instructions, merge_guard, repo_root}` to a state
file at `${XDG_STATE_HOME:-~/.local/state}/fabiandistler-agents/install.json`.
`./install.sh --update` reads the file and replays the run. With no state file
it exits with a distinct code that names `--target`. The state file stops
repetition across runs. Each write still re-checks its own entry condition
(marker present, link points into this repo), as the existing helpers already
do.

**Auto re-sync after `git pull`.** Offer an opt-in `--git-hook` that installs
`.git/hooks/post-merge` (and `post-rewrite`, for `pull --rebase`) in this
clone, calling `./install.sh --update`. The repo already uses prek. prek
supports `post-merge` stages, but the hook belongs to the user's install
state, not the repo's CI, so a plain per-clone git hook with a marker line is
simpler. It is idempotent, and `--uninstall --git-hook` removes it.

**Idempotent re-run and stale cleanup.** Both are mostly there already: links
report `ok`, blocks are written only when changed, and dangling skill links
are pruned. Two gaps remain:

- prune marker-carrying agent files whose source is gone (defect 2);
- compute the routed-member overrides from all routed categories whose router link exists, not from the `--category` filter (defect 1).

**`--check` (doctor).** A read-only verb, cheap because it reuses the dry-run
code paths. It reports one TSV row per drift item (`target`, `kind`, `path`,
`state`), where the state is missing, stale, foreign, duplicate or
untrusted-hook. Proposed exit codes: 0 clean, 3 drift found, 2 usage. Default
output is a count summary, and `--output FILE` writes the full list. It also
covers defect 3, a stale instructions block (compare the rendered block with
the file), and a clone that has moved (absolute paths in the hook command and
in the agent TOMLs).

**opencode subagents.** Convert `plugins/*/agents/*.md` to
`~/.config/opencode/agents/<name>.md`:

- keep `description`;
- add `mode: subagent`;
- map Claude `tools:` to `permission:` (no Edit or Write means `edit: deny`);
- drop `model:` (`sonnet` is not an opencode `provider/model` ID);
- resolve `${CLAUDE_PLUGIN_ROOT}`;
- mark ownership with a YAML comment.

The frontmatter parser currently lives inside `plugin_agent_toml`
(`install.sh:566`). Move it to one Python module with a Codex renderer and an
opencode renderer, so the agent-format knowledge sits in one place
(module-design rule). Use the plural `agents/`: `cleanup_opencode_legacy`
already treats the singular `agent/` as a legacy location, and it only removes
skill symlinks.

**opencode command skills without a command directory.** opencode reads
`metadata: {opencode/slash: "true", opencode/autoinvoke: "false"}` in SKILL.md
([opencode skills](https://opencode.ai/docs/skills)). This is the analogue of
the Codex `agents/openai.yaml` sidecar. With it, command skills install as
ordinary skills under opencode too. That fixes defect 5 and removes the
command-directory branch for opencode. `quick_validate.py` can then enforce the
metadata on `activation: command` skills, as it enforces the sidecar today.

**One shared skills root for Codex and opencode.** Link into `~/.agents/skills`
once. Codex reads it as its current user scope, and opencode reads it as a
compatibility root. Under a `claude` target, skip opencode's skill links,
because opencode already reads `~/.claude/skills`. Two cases still need
opencode links: skills whose `targets:` field excludes claude, and runs that
pass different `--env` or `--category` values per target. Migrate by unlinking
our own links from `~/.codex/skills` and `~/.config/opencode/skills`.

**Codex plugin marketplace.** This exists now. `codex plugin marketplace add
owner/repo` tracks a Git marketplace, and `codex plugin marketplace upgrade`
refreshes it. The ChatGPT desktop app also reads
`$REPO_ROOT/.claude-plugin/marketplace.json` as a "legacy-compatible"
marketplace and accepts Claude-compatible plugin manifests
([Codex plugins](https://developers.openai.com/plugins/build/plugins)). It
would make Codex as hands-off as the Claude marketplace, `git pull`
included. It is unproven for this repo, though:

- the docs steer installing to the desktop app, not the CLI;
- installs are copied into `~/.codex/plugins/cache/…`, and `plugins/<cat>/skills/*` are relative symlinks out of the plugin root;
- the portable components are skills, MCP and hooks only, so subagents and member disabling would stay with `install.sh`.

Run a spike before committing to it.

## 4. Ranked proposals

The ranking is value over effort (L = under a day, M = a few days).

1. **Fix defects 1 and 2: overrides derived from installed routers, and stale-agent pruning.** High value, effort L. Without these fixes, any automated re-run breaks routing or leaks files.
2. **Add `--check` (doctor) with TSV output and exit codes 0/2/3.** High value, effort L to M. It is read-only, so it is safe to run unattended, and it shows every other drift.
3. **Add a state file plus `--update`.** High value, effort M. It removes the main burden of remembering flags and is the prerequisite for item 5.
4. **Fix the opencode double-load (defect 3) and move to `~/.agents/skills` (defect 4).** High value, effort M. It fixes a visible bug and gets Codex off a deprecated path, but it needs a migration.
5. **Add an opt-in `--git-hook` (post-merge or post-rewrite running `--update`).** Medium value, effort L. Re-sync after `git pull` becomes automatic.
6. **Add `--target=detected`.** Medium value, effort L. Nothing left to remember about which agents are installed.
7. **Convert subagents to opencode agents.** Medium value, effort M. It brings opencode up to Codex parity. Do it together with extracting the parser module.
8. **Add `opencode/slash` and `opencode/autoinvoke` metadata to command skills.** Medium value, effort L. It drops the singular `command/` dependency (defect 5).
9. **Trim `--help` to about 25 lines and document the exit codes (defect 7).** Low value, effort L. It is required by the agent-script rules anyway.
10. **Switch the Codex member override from `name` to `path` (defect 6).** Low value, effort L. Use the documented selector before Codex drops the other one.
11. **Spike the Codex plugin marketplace.** Value is uncertain, effort M. It could replace symlinks for Codex skills. Spike before deciding.

## 5. Risks and constraints

- **Never prompt.** Detection, `--update` and the git hook all run headless. A missing input exits with a non-zero code naming the flag (`--target=claude|codex|opencode|all|detected`). `--update` with no state file gets its own exit code.
- **Writes into user config files.** `~/.codex/config.toml`, `~/.claude/settings.json` and the `AGENTS.md` files stay behind marker blocks or script-name matching, as today. Re-check each entry condition right before writing, not only at the start of the run. A post-merge hook makes these writes happen without the user asking, so keep it opt-in. It should print one line per change, and its first install should run `--check` before `--update`.
- **Silent target expansion.** If `--update` replays a remembered `detected`, a newly installed agent gets written to without the user asking. Store the resolved list in the state file and report new detections through `--check`, instead of acting on them.
- **Codex hook trust.** Each regenerated merge-guard hook body needs re-trust in `/hooks`. Keep the rendered hook byte-stable so that `--update` does not keep invalidating trust.
- **Migrating to `~/.agents/skills`.** Other tools write there too. Link only our own skills, prune only links that point into this repo, and warn on name collisions instead of overwriting.
- **Absolute paths.** The agent TOMLs, the planned opencode agents and the merge-guard command embed `REPO_ROOT`. A moved clone breaks them silently. `--check` should flag it, and `--update` should rewrite marker-owned files.
- **Unverified points.** Three things were not confirmed. First, whether Codex CLI (not the desktop app) installs from `.claude-plugin/marketplace.json`. Second, whether copying into the plugin cache resolves the relative skill symlinks. Third, whether a Codex custom agent can set a read-only `sandbox_mode` (the docs say agents "inherit the parent's permissions").

## Sources

- Codex skills: <https://developers.openai.com/codex/skills> (served as learn.chatgpt.com/docs/build-skills)
- Codex plugins and marketplaces: <https://developers.openai.com/plugins/build/plugins>
- Codex config reference: <https://learn.chatgpt.com/docs/config-file/config-reference>
- Codex subagents: <https://developers.openai.com/codex/subagents>
- Deprecated `~/.codex/skills` (source quote): <https://github.com/cli/cli/issues/14153>
- opencode skills (v1 and v2): <https://opencode.ai/docs/skills>, <https://opencode.ai/v2/docs/skills>
- opencode agents: <https://opencode.ai/docs/agents>
- opencode commands: <https://opencode.ai/docs/commands>
