# ADR-0004: One distribution channel per install surface

## Status

Accepted (2026-09-13)

## Context

[#149](https://github.com/fabiandistler/agents/issues/149) asked whether to
rebuild this repo "as a plugin" now that the two components requiring a local
clone are gone — `mcp-wiki-server` (`9767c91`) and `eval-suite` (`ef3b158`).

Grilling the question moved it off its own title. The motivation is not
duplication, maintenance burden, or tidiness: it is **refresh cost across two
machines**. Pulling the clone and re-running `install.sh` on both a home and a
work machine is the whole complaint. That reframes #149 from a channel question
into a refresh question, and the answer differs per surface.

The repo was already a marketplace before the issue was filed —
`.claude-plugin/marketplace.json` registers six plugins and
`plugins/<category>/skills/<name>` are symlinks into the canonical `skills/`.
What was never decided is which surface is served by which channel.

### Measured state at the time of the decision

| Surface | Skills came from | Refresh | Instruction block |
| --- | --- | --- | --- |
| `claude` | marketplace plugin; `~/.claude/skills/` held no link from this repo | automatic | `install.sh` managed block, present |
| `codex` | `install.sh` symlinks (13) **and** the `architecture` plugin from a local path | manual | `install.sh` managed block, present |
| `opencode` | `install.sh` symlinks (10) | manual | none by design; it reads `~/.claude/CLAUDE.md` |

One defect was visible in that table before any decision was taken: Codex ran
both channels at once, so `architecture` registered twice — the same fault
[#159](https://github.com/fabiandistler/agents/issues/159) reports for Claude.

### What was measured, not assumed

- **Claude refreshes itself.** `~/.claude/plugins/known_marketplaces.json` holds
  `fabiandistler-agents` with `"autoUpdate": true`, last refreshed
  `2026-09-13T13:14:45Z`. The problem #149 describes does not exist on Claude.
- **Codex reads `.claude-plugin/marketplace.json` directly.** No `.agents/` or
  `.codex-plugin/` manifest is required. Proven twice: against a local path,
  and against the GitHub URL after
  `codex plugin marketplace add https://github.com/fabiandistler/agents.git`,
  which listed all six plugins from its own clone. The relative symlinks under
  `plugins/*/skills/` survive that clone.
- **Codex does not refresh itself.** `codex plugin marketplace upgrade` is
  documented as "Refresh configured Git marketplace snapshots". Evidence that it
  is not automatic: the `ponytail` snapshot sat at `last_updated =
  2026-08-14` while ponytail shipped 4.9.0, a month stale.
- **A Codex plugin cannot ship subagents.** `validate_plugin.py` knows one
  component contract, `skills`; the scaffold offers `skills/`, `hooks/`,
  `scripts/`, `assets/`, `.mcp.json`, `.app.json`. The `agents/openai.yaml` the
  validator does read is a per-skill invocation-policy sidecar, not a subagent.
  `plugins/architecture/agents/` is therefore Claude-only and Codex ignores it.
- **No plugin format delivers standing instructions.** Claude plugins that ship
  a root `CLAUDE.md` (`mattpocock-skills`, `superpowers`) do not get it loaded
  into a session — it is repo documentation for the plugin's own development.
  The Codex plugin format has no rules component at all.
- **opencode plugins are npm packages, and they do not carry skills.** The docs
  state "Both regular and scoped npm packages are supported" and name no git
  shorthand. ponytail reaches opencode by publishing to npm and shipping a JS
  shim, `.opencode/plugins/ponytail.mjs`, that mounts its skills at runtime.
- **opencode 1.18.30 has `skills.paths`, `skills.urls` and `instructions`
  config keys.** `skills.urls` fetches from a `/.well-known/skills/` root into
  `~/.cache/opencode/skills/` — the right shape for a clone-free channel, but
  undocumented and currently broken upstream: remote skills list and then fail
  to invoke with "Skill or command not found"
  ([anomalyco/opencode#20020](https://github.com/anomalyco/opencode/issues/20020)).

## Decision

Each install surface is served by exactly one distribution channel, chosen for
its refresh behaviour rather than for uniformity.

| Surface | Channel | Refresh |
| --- | --- | --- |
| `claude` | marketplace plugin | automatic |
| `codex` | marketplace plugin, git source | `codex plugin marketplace upgrade` |
| `opencode` | `skills.paths` pointing at the clone | `git pull` |

`install.sh` stops linking skills entirely. It keeps the jobs no plugin format
can do: composing the instruction block, writing Codex's `[[skills.config]]`
member-suppression block, and generating the two Codex subagent TOMLs.

The remaining manual refresh on `codex` and `opencode` is handled by a systemd
user timer per machine, not by more manifest.

`main` stays live. No tags, no release versions.

## Decision drivers

- **Refresh is the variable under optimisation, not channel count.** Two
  channels that both refresh unattended beat one channel that does not. The
  timer, not the plugin, is what actually answers #149.
- **The Codex channel costs nothing to build.** It consumes the manifest that
  already exists. The only change is moving the marketplace source from a local
  path to the GitHub URL.
- **The routers are worth more than installer simplicity.** Codex follows
  symlinks recursively ([codex#22275](https://github.com/openai/codex/issues/22275)),
  so without the `[[skills.config]]` block the eleven router members register
  individually and progressive disclosure is lost. ADR-0002 kept the
  `architecture` router on an 88.6 % against 60.0 % measurement; giving that up
  on Codex to retire an installer would trade the stronger asset for the weaker
  one.
- **One channel per surface is a rule the tracker can check.** Both live
  double-registration faults — Codex today, Claude in #159 — are the same
  failure, and the rule names it.

## Considered options

- **One channel per surface, plus a timer (chosen).**
- **Plugin-only everywhere.** Rejected: it cannot carry the instruction block on
  any surface, and on Codex it drops the subagents and the router suppression.
- **A self-sufficient Codex plugin whose `session_start` hook writes the config
  block and the subagent TOMLs.** `hooks/` is a supported plugin component and
  ponytail already ships exactly such a hook. Rejected *for now* on a single
  argument: it buys clone-freedom, and the clone stays anyway for `opencode`
  and for the instruction block. A hook writing into `config.toml` every session
  also inherits the full write-safety discipline in
  `instructions/80-agent-pipelines.md` — re-check the entry condition
  immediately before the write, plus a state file. Too much machinery for a
  clone that does not go away.
- **Publishing to npm so opencode auto-updates.** Rejected: it requires a
  release pipeline, version discipline and a JS shim to mount skills, for the
  least capable of the three surfaces.
- **Building against `skills.urls` now.** Rejected: the feature is undocumented
  and demonstrably broken upstream.
- **Versioned releases instead of `main` = live.** Rejected: it reintroduces the
  manual step #149 exists to remove, for a single-user catalogue whose structure
  is already gated in CI.

## Consequences

- `install.sh` loses its skill-linking role on all three targets. What remains
  is instruction composition and Codex configuration. The `--instructions` flag
  stops being opt-in behaviour layered on top of skill linking and becomes what
  the installer does, which is precisely the change #159 asks for — that issue
  is resolved by this ADR rather than separately.
- [#153](https://github.com/fabiandistler/agents/issues/153) ("installer
  simplify, without always checkout and clone") is likewise answered here: the
  clone stops being an install step for `claude` and `codex`, and stops being a
  symlink source for `opencode`.
- The Codex marketplace source must move from a local path to the GitHub URL,
  and the `~/.codex/skills/` symlinks must be removed in the same change, or
  the existing double registration persists.
- `README.md` and `docs/install.md` describe skill linking as the installer's
  main job — the README's symlink quick start and flag table, and the "What gets
  linked where" and Codex sections of `docs/install.md`. Until the
  implementation lands they contradict this ADR, and a reader of either gets the
  opposite answer about what `install.sh` does. They are part of the change, not
  follow-up.
- **`--target=claude --instructions` stays mandatory for `opencode` to have any
  rules.** opencode gets no instruction file of its own on purpose: its loader
  reads `~/.claude/CLAUDE.md` unless `disableClaudeCodePrompt` is set. So
  `--target=claude` becomes a no-op for skills while remaining the only way
  opencode receives the instruction block. Do not "simplify" that target away.
- "Live" is not uniform. A push to `main` reaches Claude within a session and
  reaches Codex and opencode only after the timer fires. A bad push is visible
  on Claude first.
- The two Codex subagents stay installer-generated. They will never arrive
  through the plugin.

## Notes

Reopen the self-sufficient-plugin option (`session_start` hook) when opencode's
`skills.urls` works. At that point two of three surfaces become clone-free and
the hook is the only thing standing between the repo and a clone-free install
everywhere. Until then the clone is load-bearing and the hook earns nothing.

Deliberately not decided here:

- Whether six plugins is the right split. The category granularity mirrors
  `--category` and is out of scope.
- Whether `opencode` stays a supported surface at all. It is the cheapest to
  drop and the least capable, but nothing in #149 argued for dropping it.
