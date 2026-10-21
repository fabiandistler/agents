# Plugin-only distribution for Claude Code, Codex CLI and opencode

Research note, 2026-10-21. Question: can each agent install everything this
repo ships through its own plugin or package mechanism, so that `install.sh`
loses its `claude` target (and ideally the other two)? Evidence comes from
first-party docs, cited inline, and from hands-on tests in throwaway `$HOME`s
under the session scratchpad with these versions:

- Claude Code 2.1.306 (preinstalled);
- Codex CLI 0.162.1 (`npm i -g @openai/codex@0.162.1`, published 2026-10-09);
- opencode 1.19.0 (`npm i -g opencode-ai@1.19.0`, published 2026-10-11).

Network installs worked, so every "tested" claim below was run, not inferred.
No model turn ran for Codex or opencode (no credentials there), so anything
that needs a live model in those two is marked "read only".

## Contents

- [Answer in one paragraph](#answer-in-one-paragraph)
- [What install.sh does today](#what-installsh-does-today)
- [1. Claude Code plugins](#1-claude-code-plugins)
- [2. Codex CLI plugins](#2-codex-cli-plugins)
- [3. opencode plugins](#3-opencode-plugins)
- [4. Conclusion per agent](#4-conclusion-per-agent)
- [Tested vs read](#tested-vs-read)
- [Sources](#sources)

## Answer in one paragraph

Claude can go plugin-only. Skills, command skills, subagents and the merge
guard install through the existing marketplace as they are. The instruction
fragments need a new `core` plugin: a SessionStart hook injects the always-on
fragments, and a PostToolUse hook with an `if` path filter stands in for
`~/.claude/rules`. Both were tested end to end with a live model. Codex is
closer than the earlier note assumed. The CLI reads
`.claude-plugin/marketplace.json` directly and loads Claude-format
`hooks/hooks.json`. But it drops **every** symlink when it copies a plugin into
its cache, so today's `plugins/` tree installs as empty plugins. Codex also has
no plugin component for subagents or for disabling router members. opencode
has no marketplace. An npm or git package plugin can register skills, agents,
commands and instructions through its `config` hook (tested with a `file://`
plugin), but it needs a build step, because `npm pack` drops symlinks too.

## What install.sh does today

The Claude target of `install.sh` covers six things:

1. skill links in `~/.claude/skills`;
2. `activation: command` skills as `~/.claude/commands/<name>.md`;
3. subagents, already shipped only through the plugin, since `install.sh` has none for Claude;
4. `--instructions`: the managed block in `~/.claude/CLAUDE.md`;
5. `--instructions`: path-scoped fragments (today only `40-r`) as `~/.claude/rules/agents-*.md`;
6. `--merge-guard`: a PreToolUse entry in `~/.claude/settings.json`.

## 1. Claude Code plugins

### Skills, command skills, subagents (tested)

`claude plugin marketplace add <local clone>` and
`claude plugin marketplace add fabiandistler/agents` both work against the
repo as it is. `claude plugin install architecture@fabiandistler-agents`
copies the plugin to `~/.claude/plugins/cache/<mkt>/<plugin>/<sha12>/`.

- **Symlinks.** The skill symlinks (`plugins/<cat>/skills/x -> ../../../skills/x`) and the router member links come out as real directories in the cache, zero symlinks left. The docs explain this: a symlink to "elsewhere within the same marketplace" is dereferenced, one inside the plugin is preserved, and one outside the marketplace is skipped ([host-marketplace](https://code.claude.com/docs/en/plugins/host-marketplace#share-files-within-a-marketplace-with-symlinks)).
- **Routers.** `claude plugin details architecture@…` lists `Skills (1) architecture` and `Agents (2) coupling-analyst, cohesion-analyst`. The nested members stay hidden, as they do with `install.sh`.
- **Command skills.** They load as plugin skills, and `disable-model-invocation: true` keeps them user-only. They become namespaced: `/tldr` turns into `/communication:tldr`.

### Merge guard as a plugin hook (tested)

A plugin's `hooks/hooks.json` uses the same shape as `settings.json` hooks
([plugins-reference](https://code.claude.com/docs/en/plugins-reference)). A
spike plugin carried `scripts/pr_merge_guard.py` and this PreToolUse entry:
`matcher "^(Bash|mcp__.*)$"`, command
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pr_merge_guard.py" --harness claude`.
`claude -p --plugin-dir … --allowedTools Bash` was asked to run
`gh pr merge 99999 --repo nonexistent-owner-zz/nonexistent-repo-zz`, and the
hook blocked it with the guard's own message, naming the `core@inline` plugin.
The script has to live inside the plugin, because `${CLAUDE_PLUGIN_ROOT}`
points at the versioned cache directory.

### Instruction fragments

**There is no rules or CLAUDE.md component.** The standard layout lists skills,
commands, agents, hooks, MCP, LSP, output styles, workflows, themes, monitors,
`bin/` and `settings.json`. A plugin `settings.json` honours only `agent` and
`subagentStatusLine`. "A `CLAUDE.md` at the plugin root isn't loaded as
context" ([plugins-reference](https://code.claude.com/docs/en/plugins-reference#standard-layout)).
`claude plugin validate` warns about a root `CLAUDE.md` (tested). It ignores a
`rules/` directory without a word, so a rules directory would ship and silently
do nothing.

**Always-on core through SessionStart `additionalContext` (tested).** A hook
script that concatenates `instructions/*.md` and prints
`{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":…}}`
works. A headless run quoted the first bullets of "Bug fixing" and "Agent
pipelines" verbatim, and a control run without the plugin answered "ABSENT".
There is one trap. All 10 fragments in one string (12.5k chars) came back as "a
truncated preview … the rest was saved to a file". That matches the documented
10,000-char cap per hook output ([hooks](https://code.claude.com/docs/en/hooks)).
Split the fragments across several hook handlers, each under 10k (two handlers
of 7.9k and 4.7k worked), or ship only the Tier A core proposed in
`instruction-loading-alternatives.md`. Use the matcher
`startup|resume|clear|compact`, so the context comes back after compaction.

**Path-scoped rules through PostToolUse + `if` (tested).** A hook with
`matcher "Read|Edit|Write"` and handler `"if": "Read(**/*.R)"` ran a script
that emits the body of `40-r.md`. After `Read R/f.R` the model quoted the first
R bullet and noted it "came from the hook context that arrived after the Read
call". After `Read notes.txt` it answered ABSENT.

**What is lost compared with `~/.claude/rules`:**

- **Repeat cost.** A rule loads once per session and again after compaction. The hook fires on every matching call, so the script needs a per-session dedupe (state in `${CLAUDE_PLUGIN_DATA}`, keyed by `session_id`, reset by a SessionStart `compact` handler).
- **One `if` per handler.** `if` takes a single permission-rule pattern. The seven globs in `40-r` become seven handlers, or one broad handler that filters on `tool_input.file_path` in the script.
- **Timing.** The context arrives next to the tool result, after the tool ran. That is the same as a read-triggered rule, but for Write/Edit the first write has already landed.
- **Framing.** Rules and CLAUDE.md load as memory. Hook output is a system reminder. Whether adherence differs was not measured.
- **Fail-safe direction flips.** A broken rule frontmatter loads the rule unconditionally ([memory](https://code.claude.com/docs/en/memory)). A broken hook (no `python3`, a crash) loads nothing, without any error the model sees.
- **Hook-free surfaces.** Not verified: whether claude.ai and Cowork run plugin hooks. The component-support table is at [platform-support](https://claude.com/docs/plugins/platform-support#compare-component-support-by-app).

### Updates

From [plugins/loading](https://code.claude.com/docs/en/plugins/loading):

- **Version.** It is computed from the manifest `version`, then the entry `version`, then the git commit SHA. No `version` field exists today, so every commit is a new version. Keep it that way, or every user stays pinned.
- **Auto-update is off by default** for third-party marketplaces. Users turn it on with the `/plugin` Marketplaces toggle, or with `"autoUpdate": true` on the `extraKnownMarketplaces` entry. When it is on, the update pass runs up to ten minutes after the first message. It updates on disk and asks for `/reload-plugins`. `DISABLE_AUTOUPDATER=1` turns it off unless `FORCE_AUTOUPDATE_PLUGINS=1` is set.
- **Manual update.** `claude plugin update <name>@<mkt>`. A marketplace added from a local path loads relative-path plugins in place, so a `git pull` is enough there.
- **Old versions.** Each one gets an `.orphaned_at` marker and is removed 14 days later.

## 2. Codex CLI plugins

### Marketplace and install (tested)

The earlier unverified point 1 is resolved. `codex plugin marketplace add
<path>` and `codex plugin marketplace add fabiandistler/agents` both read
`.claude-plugin/marketplace.json` and list all six plugins.
`codex plugin add workflow@fabiandistler-agents` installs into
`~/.codex/plugins/cache/<mkt>/<plugin>/local/` and writes
`[plugins."workflow@fabiandistler-agents"] enabled = true` to `config.toml`.
A Git marketplace is cloned to `~/.codex/.tmp/marketplaces/<name>/`.

### Symlinks: dropped, all of them (tested)

The earlier unverified point 2 is resolved, negatively. After install,
`plugins/workflow/…/skills/` in the cache is **empty**. This holds for both
local and Git sources. A spike with a symlink that pointed *inside* the plugin
(`skills/tldr -> ../real/tldr`) lost it too. Only the real directory next to it
(`skills/was`) survived. Codex keeps no symlinks at all, unlike Claude.

With a fully dereferenced copy (`cp -rL`), `codex debug prompt-input` lists the
plugin skills as `architecture:architecture`, `workflow:natural-planning`, and
so on:

- **Command skills** stay out of the list. The `agents/openai.yaml` sidecar (`allow_implicit_invocation: false`) is honoured inside plugins.
- **Router members** are all listed (`architecture:ddd`, `architecture:c4-modeling` …), because Codex scans `skills/` recursively. So progressive disclosure breaks again.
- **Disabling members** works with `[[skills.config]] name = "architecture:ddd"` or `path = "<cache>/…/SKILL.md"` plus `enabled = false` in `config.toml` (tested, both selectors). A plugin cannot ship that config.

### Hooks (tested, discovery only)

The docs scope bundled lifecycle hooks to "manually installed Codex desktop
plugins" ([Codex plugins](https://developers.openai.com/plugins/build/plugins#bundled-mcp-servers-and-lifecycle-hooks)).
The CLI loads them anyway. The app-server `hooks/list` call returned our
Claude-format `hooks/hooks.json` entries with `source: "plugin"`. It had
resolved `${CLAUDE_PLUGIN_ROOT}` to the absolute cache path and set
`trustStatus: "untrusted"`. Per the docs, plugin hooks are skipped until the
user trusts the current definition in `/hooks`, and Codex sets both
`PLUGIN_ROOT` and `CLAUDE_PLUGIN_ROOT`.

So one `hooks/hooks.json` can serve both agents. There are two caveats:

- **No `if` field.** The Codex hook list shows no handler-level `if` (Codex documents matchers only), and Codex has no `Read` tool. A path-scoped rule hook must filter paths inside the script, and in Codex it sees edits only (`apply_patch` matches `Edit|Write`).
- **Model effect not run.** Whether SessionStart `additionalContext` reaches a Codex model, and under what size cap, is read only. The docs say it is "added as extra developer context" ([Codex hooks](https://learn.chatgpt.com/docs/hooks)), and `hooks/list` reports `additionalContextLimit: null`.

### Subagents (tested: absent)

The app-server `plugin/read` call returns `skills`, `hooks`, `apps`,
`mcpServers` and `scheduledTasks`, but no agents. A prompt rendered with the
architecture plugin installed does not mention `coupling-analyst`. The portable
components are skills, `mcp.json`, hooks and assets
([Codex plugins](https://developers.openai.com/plugins/build/plugins#plugin-structure)).
Custom agents stay in `~/.codex/agents/*.toml`
([Codex subagents](https://developers.openai.com/codex/subagents)).

### Upgrades

- **Git marketplaces.** `codex plugin marketplace upgrade [name]` refreshes the snapshot ([Codex plugins](https://developers.openai.com/plugins/build/plugins#add-a-marketplace-from-the-cli)). Tested: the first run printed "Upgraded 1 marketplace(s)". Not verified: whether it also refreshes an installed plugin's cache. The docs only say Codex "can install or refresh files for configured plugins" during a refresh, and the cache version is `local` for Git sources too.
- **Local marketplaces.** Tested: an edit to the source does not reach the cache, not even at session start. A second `codex plugin add` does copy it.
- **`file://` Git URLs** are rejected ("invalid marketplace source format").

## 3. opencode plugins

opencode has no marketplace. Its distribution unit is a JS plugin, loaded from
`~/.config/opencode/plugins/`, from npm through `"plugin": [...]`, or from a
path or `file://` URL ([opencode plugins](https://opencode.ai/docs/plugins)).
`opencode plugin <module>` installs it and edits the config.

### What a plugin can register (tested, config level)

The v1 `Hooks` type in `@opencode-ai/plugin@1.19.0` has
`config?: (input: Config) => Promise<void>`, which mutates the merged config. A
`file://` spike plugin pushed four things in that hook:

- `skills.paths` (its own `skills/` dir);
- `instructions` (`<pkg>/instructions/*.md`);
- `agent["spike-analyst"]` (`mode: subagent`, `permission.edit: deny`);
- `command["spike-tldr"]`.

`opencode debug config` showed all four. `opencode debug skill` listed both
skills, including one reached through a symlink, and
`opencode debug agent spike-analyst` resolved the agent. Not run: a model turn
confirming that the instruction files reach the prompt. The docs say that
`instructions` accepts paths, globs and remote URLs (fetched with a 5 s
timeout), and that all of them are "combined with your AGENTS.md files"
([opencode rules](https://opencode.ai/docs/rules)). The merge guard already
exists as an opencode plugin (`scripts/opencode/pr-merge-guard.js`), so it
folds into the same package.

### Gaps

- **Packaging drops symlinks.** `npm pack --dry-run` on the spike left out the symlinked skill (tested). An npm package needs dereferenced copies built at publish time. opencode v2 accepts npm-compatible Git specs (`github:owner/repo#ref::path:sub`) ([opencode v2 plugins](https://opencode.ai/v2/docs/plugins)). Untested: whether a Git install keeps symlinks and whether v1 accepts Git specs.
- **Path scoping** has no declarative form. `tool.execute.after` could append a fragment to a matching read's output. That is untested and would be per-agent code.
- **Two plugin APIs.** v2 uses the `plugins` key (plural), `ctx.skill.transform`, `ctx.agent.transform`, `ctx.command.transform` and `ctx.session.hook("context")` for system text. One default export can carry both v1 `server()` and v2 `setup()` ([opencode v2 plugin API](https://opencode.ai/v2/docs/build/plugins#support-v1)). The merge-guard plugin already does this.
- **Updates.** v2 checks unpinned npm and Git plugins at startup "without changing the installed package"; `opencode plugin update` applies them, and exact versions stay pinned ([opencode v2 plugins](https://opencode.ai/v2/docs/plugins#manage)). v1 installs npm plugins with Bun at startup into `~/.cache/opencode/node_modules/`. Its refresh rule is not documented.
- **Side effect of Claude going plugin-only.** opencode reads `~/.claude/skills` as a compatibility root ([opencode skills](https://opencode.ai/docs/skills)). Once Claude stops linking there, opencode loses that source, which also removes the double-load defect 3 in `installer-automation.md`.

## 4. Conclusion per agent

### Claude Code: plugin-only is feasible

**Covered by plugins.** Skills, command skills, subagents and routers work
today as they are. The merge guard needs a hook plugin. The instructions need a
`core` plugin with SessionStart handlers (each under 10k chars) and PostToolUse
`if` handlers for the path-scoped fragments. Put the merge guard in its own
plugin, so it stays opt-in as `--merge-guard` is today.

**Stays outside plugins.** The `.claude/` mirror for cloud sessions
(`scripts/build_project_claude.py`), because cloud sessions do not add
repo-declared marketplaces ([plugins/loading](https://code.claude.com/docs/en/plugins/loading#plugins-shared-through-a-repository)).
A one-time migration (`--uninstall --target=claude`) to remove the old links,
the CLAUDE.md block, the rules and the settings entry. Otherwise skills load
twice: once as `/tldr`, once as `/communication:tldr`.

**Migration risks:**

- **`--env` filtering is gone.** Plugins split by category, not by coding/chat.
- **Commands are renamed** to `<plugin>:<name>`.
- **Auto-update is off** unless the user enables it.
- **Instructions depend on `python3` and hook health.** A failing hook silently drops all rules.
- **Hook framing is new.** It is a system reminder, not memory, so re-check adherence after the switch.
- **Fragment size needs a gate.** Add a CI check that keeps each SessionStart payload under 10,000 chars.

### Codex CLI: partial, needs a repo change first

**Covered by plugins.** Skills, command skills (via the sidecar), and hooks for
the merge guard and the instructions. Hooks need a one-time trust review in
`/hooks`. They are untested with a live model.

**Blockers:**

- **Symlinks.** `plugins/<cat>/` must hold real files. Either invert the layout (real files under `plugins/`, `skills/<name>` as symlinks into them) or publish a generated, dereferenced tree on a branch and pin the marketplace to it with `--ref`. Claude handles both.
- **Router members.** They register as top-level skills. Either `install.sh` keeps writing `[[skills.config]] enabled = false`, or members move out of the router's `skills/` subtree. That second option is untested, and it changes the router's relative member paths for every agent.

**Stays in `install.sh`.** Subagent TOMLs (no plugin component), and the member
disable block unless the layout changes.

**Risks.** The CLI docs still steer installs to the desktop app. The snapshot
lives under `~/.codex/.tmp/`. Upgrade propagation into the plugin cache is
unverified.

### opencode: possible as an npm or Git package, not a marketplace

**Covered by a package plugin.** Skills (`skills.paths`), subagents (`agent`,
converted from the Markdown), commands (`command`, or skills with
`opencode/slash` metadata), instructions (`instructions`, file or URL), and the
merge guard. All of this goes through one `config` hook (tested at config level).

**Costs:**

- a JS package plus a publish or build step that dereferences symlinks;
- a v1 and v2 dual export;
- no path scoping.

**Stays in `install.sh`.** Nothing is strictly needed once the package exists.
Until then, keep the current opencode target.

**Risks.** A one-line config entry replaces a symlink tree, which is cheaper to
undo. Loading the user's config into a plugin's hook, though, means our code
runs at every opencode startup. A `config` hook bug can break startup, because
opencode "hard-fails on invalid config".

## Tested vs read

**Tested hands-on:**

- Claude marketplace add (local and GitHub), install, symlink dereferencing, router hiding, `plugin details`;
- Claude SessionStart context, including the 10k truncation;
- Claude PostToolUse `if` path rule, positive and negative;
- Claude merge-guard block;
- Codex marketplace add (local and GitHub) from `.claude-plugin/marketplace.json`;
- Codex symlink loss (local, GitHub, in-plugin);
- Codex dereferenced skill listing, sidecar honoured, members exposed, member disable by name and by path;
- Codex plugin hook discovery and trust state, no agents in `plugin/read`, local-source refresh behaviour;
- opencode `config`-hook injection of skills, agents, commands and instructions;
- `npm pack` dropping symlinks.

**Read only:**

- Codex hook effect on a live model and its size cap, plus upgrade propagation;
- opencode instruction delivery to the model, v1 update rules, Git plugin specs;
- Claude hook support in claude.ai and Cowork.

## Sources

- Claude plugin manifest and layout: <https://code.claude.com/docs/en/plugins-reference>
- Claude plugin loading, versions, auto-update: <https://code.claude.com/docs/en/plugins/loading>
- Claude marketplace symlink handling: <https://code.claude.com/docs/en/plugins/host-marketplace#share-files-within-a-marketplace-with-symlinks>
- Claude hooks: <https://code.claude.com/docs/en/hooks>
- Claude memory and rules: <https://code.claude.com/docs/en/memory>
- Claude plugin support per app: <https://claude.com/docs/plugins/platform-support>
- Codex plugins and marketplaces: <https://developers.openai.com/plugins/build/plugins>
- Codex hooks: <https://learn.chatgpt.com/docs/hooks>
- Codex subagents: <https://developers.openai.com/codex/subagents>
- opencode plugins (v1): <https://opencode.ai/docs/plugins>
- opencode config: <https://opencode.ai/docs/config>
- opencode rules and `instructions`: <https://opencode.ai/docs/rules>
- opencode skills: <https://opencode.ai/docs/skills>
- opencode v2 plugins and plugin API: <https://opencode.ai/v2/docs/plugins>, <https://opencode.ai/v2/docs/build/plugins>
