# Loading instruction fragments on demand

Research date: 2026-10-21. Question: which of the 10 fragments in
`instructions/` must stay in the always-loaded managed block, and which
first-party mechanism in Claude Code, Codex CLI and opencode can load the rest
only when needed.

## Contents

- [Finding in one paragraph](#finding-in-one-paragraph)
- [Inventory](#inventory)
- [Mechanisms per agent (verified)](#mechanisms-per-agent-verified)
- [Not verified](#not-verified)
- [Proposed mapping](#proposed-mapping)
- [Tradeoffs](#tradeoffs)
- [Sources](#sources)

## Finding in one paragraph

The whole set is about 2.9k tokens (Codex/opencode) or 2.3k (Claude, with R
already path-scoped), so the token saving is modest, about 1.5k per session.
The larger gain is adherence: Claude's docs say longer instruction files
"reduce adherence". Only Claude Code has a declarative, model-free conditional
loader for instructions (path-scoped rules). Codex and opencode have none for
global rules. Their only on-demand options are skills, which the model
triggers, and hooks or plugins. That leaves three tiers. Keep a small
always-on core. Path-scope the language rules for Claude. Move the
task-specific fragments into skills or reference files, with a one-line
pointer left in the core so the model knows they exist.

## Inventory

Token estimates are body bytes / 4. "Relevant when" is my reading of the
content.

| Fragment (words, ~tokens) | `paths:` | Relevant when |
|---|---|---|
| 20-coding-standards (276, ~430) | no | Any code change; parts only when adding deps or templates |
| 25-module-design (110, ~160) | no | Designing or splitting modules or files |
| 30-python (305, ~490) | no | Python files; ~70% is the new-project `uv` baseline |
| 40-r (352, ~580) | yes (Claude only) | R package files |
| 50-dev-practices (34, ~50) | no | Committing or opening a PR (nearly always in coding) |
| 55-bug-fixing (69, ~95) | no | Fixing a reported bug |
| 60-code-comments (18, ~30) | no | Any edit |
| 70-code-review-conventions (153, ~220) | no | Reviewing a diff or PR only |
| 80-agent-pipelines (353, ~560) | no | Building LLM or agent pipelines only (rare) |
| 85-agent-scripts (183, ~280) | no | Writing a script, hook or CLI an agent runs |

Total: ~1,850 words, ~2.9k tokens. About 1.6k tokens (30, 70, 80, 85) cover
one kind of task each.

## Mechanisms per agent (verified)

### Claude Code

- **Path-scoped rules** (`~/.claude/rules/*.md` with `paths:`): "A path-scoped
  rule loads when Claude uses the Read, Write, or Edit tool on a matching
  file", including a single-file `cat`/`head`. User-level rules apply "to every
  project on your machine". After compaction they "load again on demand". If
  the frontmatter does not parse, the rule loads unconditionally. Rules without
  `paths` load at launch. [memory]
- **`@imports` do not save context**: "imported files also load at launch".
  [memory]
- **Nested `CLAUDE.md`** in subdirectories loads lazily. That is per-repo, so
  it does not help global rules. [memory]
- **Skills**: only the description is in context, and "full skill content only
  loads when invoked". A `paths:` frontmatter field exists: "Claude loads the
  skill automatically only when working with files matching the patterns".
  The listing is capped at 1,536 chars per skill. After compaction, invoked
  skills are re-attached at up to 5k tokens each, 25k in total, newest first,
  so older skills can drop out. [skills]
- **Hooks with `additionalContext`**: supported on SessionStart,
  UserPromptSubmit, PreToolUse, PostToolUse and others. PreToolUse/PostToolUse
  context is placed "next to the tool result", so Claude sees it after the tool
  has run, not before. The handler-level `if` field filters by path
  (`Edit(**/*.py)`) on tool events. UserPromptSubmit has the prompt text, so a
  keyword match is possible. Each string is capped at 10,000 chars.
  `InstructionsLoaded` is observability only and cannot inject context. [hooks]

### Codex CLI

- **AGENTS.md chain**: built "once per run" from `~/.codex/AGENTS.md` (or
  `AGENTS.override.md`) plus one file per directory from the project root
  *down to the cwd*. The combined size is capped at `project_doc_max_bytes`
  (32 KiB). Nothing below the cwd loads lazily, and there is no path-scoped
  or conditional instruction file. [codex-agents]
- **Skills**: name, description and path start in context, and the body loads
  when the skill is selected (implicitly by description, or explicitly with
  `$skill`). The list is capped at 2% of context by default (8,000 chars if the
  window is unknown). Descriptions are shortened first, and then skills may be
  omitted. `skills.max_context_tokens` raises the cap to at most 10k tokens.
  `policy.allow_implicit_invocation: false` in `agents/openai.yaml` disables
  model triggering. User skills live in `~/.agents/skills`. The docs mention
  no path-based activation. [codex-skills]
- **Hooks**: on by default (`[features] hooks`). Hooks need a one-time trust
  review in `/hooks`, re-done when a hook changes. SessionStart and
  UserPromptSubmit stdout or `additionalContext` "is added as extra developer
  context". PostToolUse `additionalContext` is too. The matcher filters the
  tool name; `apply_patch` also matches `Edit|Write`, and `tool_input.command`
  carries the patch (so file paths can be parsed from it). UserPromptSubmit
  ignores matchers, so the script must filter the prompt itself. [codex-hooks]

### opencode

- **Global rules**: `~/.config/opencode/AGENTS.md`. `~/.claude/CLAUDE.md` is
  read only if that file is missing. [oc-rules]
- **`instructions` config** (files, globs, URLs): always loaded, "combined
  with your AGENTS.md files". The globs pick files, not activation conditions.
  [oc-rules] [oc-v2]
- **Lazy loading by instruction**: the docs suggest telling the agent in
  AGENTS.md to "use your Read tool to load it on a need-to-know basis" for
  `@file` references. opencode itself does not parse them. [oc-rules]
- **Nested AGENTS.md** (v2) loads when the agent reads or lists inside that
  area. That is per-repo only. [oc-v2]
- **Skills**: listed in the `skill` tool description and loaded by
  `skill({name})`. Locations include `~/.claude/skills` and `~/.agents/skills`.
  `opencode/autoinvoke: "false"` hides a skill from auto-selection. Per-agent
  `permission.skill` patterns exist. There is no path activation. [oc-skills]
- **Plugins**: `tool.execute.before/after` hooks exist, and
  `experimental.session.compacting` can add context to the compaction prompt.
  [oc-plugins]

## Not verified

- **Claude skill `paths:`**: the docs don't say whether a matching file
  *injects* the skill body or only makes the skill eligible for the model to
  invoke. Test before relying on it.
- **Write-triggered rules in Claude**: the docs list Write as a trigger but
  don't say whether the rule arrives before or after the first write lands.
  `docs/install.md` currently says "nothing loads before the first matching
  read". It should be re-tested against the current wording.
- **Codex PreToolUse `additionalContext`**: the scraped page showed it for
  SessionStart, UserPromptSubmit and PostToolUse only. I could not read the
  PreToolUse output section.
- **Codex "Rules" page** (`learn.chatgpt.com/docs/agent-configuration/rules`):
  blocked by the session proxy. I assume it covers command-execution policy,
  not instructions, but I could not confirm it.
- **opencode plugin context injection**: the docs list no plugin event that
  adds model-visible context mid-session outside compaction.
- **Claude output styles**: not fetched. They change the system prompt for
  every session, so they are not a conditional mechanism in any case.
- `developers.openai.com/codex/*` now redirects to `learn.chatgpt.com/docs/*`.
  Direct fetches were blocked, so I read the pages via a scraping service.

## Proposed mapping

**Tier A, always-on core in all three blocks** (~800 tokens): 20, 25, 50, 55,
60. Each is short or applies to any code edit, and moving 55 (95 tokens) or
50 (50 tokens) would cost more in triggering risk than it saves. Option: split
20 and move its dependency and template bullets (~150 tokens) into a skill.

Tier A also gets **pointers**: one line per moved fragment, naming the
situation and an absolute file path, for example "Before reviewing a diff, read
`~/.agents/instructions/70-code-review-conventions.md`". `install.sh` would
copy the fragments to a fixed location and render these lines. This is the
lazy-load pattern opencode documents. It works in every agent because it only
needs a file read.

**Tier B, path-scoped (Claude)**:

| Fragment | Claude | Codex / opencode |
|---|---|---|
| 40-r | rule, as today | keep in block, or pointer |
| 30-python | rule: `**/*.py, **/pyproject.toml, **/uv.lock` | pointer; optional Codex PostToolUse hook on `apply_patch` that injects it once when the patch touches `*.py` |

For 30-python, also add a Claude PreToolUse hook (`if: Bash(uv init*)`) that
injects the fragment. A new project runs `uv init` before any `.py` file
exists, so the path rule would miss the baseline step. The context arrives
with the tool result, which is when the `uv add --dev` step happens anyway.

**Tier C, task-specific, as skills or pointers**:

| Fragment | Claude | Codex / opencode |
|---|---|---|
| 70-review | pointer, plus a `references/` page for the review skills | pointer |
| 80-pipelines | page under `llm-application-engineering/references/`, plus pointer | same (installed skill), plus pointer |
| 85-agent-scripts | pointer; optional path rule on `**/scripts/**, **/hooks/**, **/bin/**` | pointer |

80 fits the existing `ai-ml` router: `llm-application-engineering` already
holds `agent-engineering-conventions.md`, so this adds no new trigger entry.
In this repo, 85 stays loaded through `AGENTS.md` regardless.

Estimated always-on cost afterwards: Claude ~0.9k tokens (from ~2.3k), Codex
and opencode ~0.9k (from ~2.9k), not counting any optional hooks.

## Tradeoffs

- **Path rules** are model-free and reliable once a file is touched. They are
  blind to the *first* action of a task (scaffolding via Bash, planning before
  any read) and to anything without a file pattern (reviews, pipelines). If
  the YAML is malformed, the rule silently becomes always-on.
- **Skills and pointers** depend on the model deciding to load them. A missed
  trigger means the rule silently does not apply, with no error. Pointers sit
  in the always-on block, so they are more visible than one skill among many.
  Codex skill descriptions get shortened or dropped when the 2% budget fills.
  In Claude, an invoked skill can drop out after compaction if many were
  invoked.
- **Hooks** are deterministic but per-agent code: three hook formats, Codex
  trust review, and Claude's tool-event context arrives after the tool ran.
  The repo's rule "a hook is model-free" holds, but it means writing and
  testing a script per harness. Use hooks only where the timing gap matters
  (30-python baseline).
- **Do nothing**: ~2.9k tokens is about 1.5% of a 200k window. If adherence is
  not measurably worse, Tier A plus moving only 80 and 70 (~780 tokens, the
  two rarest) captures most of the benefit with the least machinery.

## Sources

- [memory] https://code.claude.com/docs/en/memory
- [skills] https://code.claude.com/docs/en/skills
- [hooks] https://code.claude.com/docs/en/hooks
- [codex-agents] https://developers.openai.com/codex/guides/agents-md (now https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [codex-skills] https://developers.openai.com/codex/skills (now https://learn.chatgpt.com/docs/build-skills)
- [codex-hooks] https://developers.openai.com/codex/hooks (now https://learn.chatgpt.com/docs/hooks)
- [oc-rules] https://opencode.ai/docs/rules
- [oc-v2] https://opencode.ai/v2/docs/instructions
- [oc-skills] https://opencode.ai/docs/skills
- [oc-plugins] https://opencode.ai/docs/plugins
