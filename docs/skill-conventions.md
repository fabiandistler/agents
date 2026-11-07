# Skill conventions

The reference for adding, renaming or changing a skill in this repository: its
frontmatter, scripts and references, the generated files, and the checks that
enforce them. [`AGENTS.md`](../AGENTS.md) points here;
[`contributing.md`](contributing.md) puts the steps in order.

## Contents

- [Router members](#router-members)
- [Conventions for skill authors](#conventions-for-skill-authors)

## Router members

Claude registers only top-level skills, so the members stay hidden there. Codex
discovers skills recursively and follows symlinks
([openai/codex#22275](https://github.com/openai/codex/issues/22275)), so it
would otherwise register each nested `members/<name>/SKILL.md` as its own skill;
`install.sh --target=codex` therefore disables every nested member by path in
`~/.codex/config.toml` (a managed `[[skills.config]]` block, `enabled = false`),
dropping them from the model's skill list. `--uninstall` removes the block.

## Conventions for skill authors

- A skill lives in `skills/<skill-name>/` and has a `SKILL.md` at its root.
- `SKILL.md` starts with YAML frontmatter providing at minimum:
  - `name` — must match the directory name (`scripts/quick_validate.py` enforces it).
  - `category` — one of `architecture`, `refactoring`,
    `ai-ml`, `workflow`, `communication`, `personal` (the fixed list in
    `scripts/catalogue.py`; `scripts/quick_validate.py` mirrors it so the
    validator also works on skills outside this repo). Determines the
    catalogue section, the `install.sh --category` subset, and which plugin
    bundles the skill.
  - `description` — single paragraph; the first sentence becomes the
    `summary` in `skills.json` (for a router the whole description does, since
    it is the category's entire trigger surface). Keep it within the description budget:
    **≤250 chars** for most skills, **≤450 chars** for router skills, **≤400 chars**
    for the small allowlist of high-traffic skills in
    `scripts/check_descriptions.py`. Descriptions
    are always-loaded metadata that competes for a tight context budget
    (Codex CLI truncates the skill list past ~2% of context), so move
    trigger lists and feature enumerations into the SKILL.md **body** (a
    leading `## When to use` section) rather than the frontmatter. CI
    enforces this with `python3 scripts/check_descriptions.py`, which also
    caps the aggregate across all `auto` skills.
- Optional frontmatter fields:
  - `activation` — `auto` (default) or `command`. `auto` skills are
    model-triggered and their description counts toward the auto-trigger
    budget. `command` skills are user-invoked only: OpenCode exposes them as
    slash commands from the ordinary skills directory when `metadata` sets
    `opencode/slash: "true"` and `opencode/autoinvoke: "false"`; Claude loads
    them from the plugins as `/<category>:<name>`. Codex custom prompts are
    deprecated, so under codex they install
    into `~/.agents/skills/` like any skill, gated by an `agents/openai.yaml`
    sidecar (`policy.allow_implicit_invocation: false`) that keeps Codex from
    auto-triggering them. That sidecar is committed per skill, at
    `skills/<name>/agents/openai.yaml` — `install.sh` links it, it does not
    generate it. For Claude, pair `command` with
    `disable-model-invocation: true` in the same frontmatter (the runtime
    realization Claude honors; ignored elsewhere). CI enforces both with
    `scripts/quick_validate.py`.
  - `when_to_use` — trigger phrases for a **router**, as a single paragraph.
    Claude Code appends it to the description in its skill listing (joined
    with `" - "`, the two capped at 1,536 chars together), so it holds the
    situations users actually type without spending the router's ≤450-char
    description budget on them. Codex ignores the key entirely (verified with
    `codex debug prompt-input`), which is why
    `scripts/check_descriptions.py` keeps it out of the Codex-facing budgets
    and gives it Claude's combined cap instead. A router's `skills.json`
    summary appends it the same way Claude does, so the recall menu in
    `eval-suite/recall` ([fabiandistler/eval-suite](https://github.com/fabiandistler/eval-suite))
    shows what the client shows.
  - `compatibility` — runtime / language requirements in plain prose.
  - `environments` — comma-separated list of the environments the skill
    belongs to: `coding`, `chat`, or both (e.g. `environments: coding, chat`).
    `install.sh --env=coding|chat` uses this to install only the matching
    subset. A skill without the field belongs to every environment.
  - `targets` — comma-separated subset of `claude`, `codex`, `opencode`
    (e.g. `targets: codex, opencode`). `install.sh` never links the skill for
    an agent the field leaves out, and removes a link it had created there
    before. Use it when a runtime already ships an equivalent of its own. A
    skill without the field is installed for every target. Because `plugins/` is
    the Claude distribution, a skill that excludes `claude` also gets no
    plugin symlink (`scripts/check_plugins.py` knows this).
  - `metadata.version` — semver-ish string.
  - `argument-hint` — the argument a `command` skill takes, shown by Claude
    Code next to the command name (e.g. `argument-hint: "<owner>/<repo>"`).
    Other agents ignore it.
  - `license`, `allowed-tools` — Agent Skills format fields that
    `scripts/quick_validate.py` accepts. No skill here uses them yet.
- The body is plain Markdown. Avoid agent-specific vocabulary
  (slash-commands, "the Skill tool", proprietary tool names, hardcoded
  install paths, runtime error text). Prefer
  describing the workflow in terms any reader can apply.
- Cross-skill references name only registered, model-invocable skills.
  A `command` skill is user-invoked, so say suggest the user run it instead
  of invoking it. A router member is read via its router file, never invoked
  by a namespaced name; name the router and the member file to read.
  CI enforces this with `python3 scripts/check_skill_refs.py`.
- Generated files — `skills.json`, the router member tables and the
  `.claude/` mirror — are regenerated by the prek commit hooks
  (`build-manifest`, `build-routers`, `build-project-claude` in
  `.pre-commit-config.yaml`) whenever a commit touches a `SKILL.md`, an
  instruction fragment or a plugin subagent. On drift the hook rewrites
  the files and fails the commit; stage them and commit again. Without the
  hooks installed (`prek install`), or after deleting a skill (deletions
  never trigger a hook), regenerate by hand in this order:
  `python3 scripts/build_manifest.py`, `python3 scripts/build_routers.py`,
  `python3 scripts/build_project_claude.py`. CI's `--check` gates catch
  whatever slips through.
- `prek install` also installs a commit-msg hook (`scripts/check_commit_msg.py`,
  Conventional Commits subjects) and two pre-push hooks that run
  `scripts/check_all.sh --skip prek,mermaid,bats` and
  `scripts/check_all.sh --only bats`; set `PYTHON=` to a 3.11+ interpreter, or
  the push stops with exit 4.
- Shell scripts are tested with Bats: one `test/<script>.bats` suite per
  entry point (`install.sh` is split into `test/install*.bats`), run by
  `test/bats/bats-core/bin/bats test/` after `git submodule update --init`.
  The rule and its exemptions are `instructions/45-shell-scripts.md`; shared
  setup lives in `test/test_helper.bash`. The bats-core, bats-support and
  bats-assert submodule pins are bumped by hand, to release tags.
- The catalogue and plugin checks below read `skills.json`, not the
  `SKILL.md` files, so a stale manifest makes them answer from stale
  metadata — regenerate it before running them locally, and that is why
  `build_manifest.py --check` is the first CI gate. Two readers stay
  independent on purpose: `scripts/quick_validate.py` parses frontmatter
  itself, so it validates the source rather than the generator's output,
  and `install.sh` reads it in bash, so skill linking never depends on
  `python3`.
- After adding, renaming, or removing a skill, update both catalogue
  tables by hand — `README.md` and `AGENTS.md` (`## Skill catalogue`) —
  keeping their text identical and each skill under the section matching
  its `category`. CI enforces this with `python3 scripts/check_docs.py`.
- Keep the plugin in sync for **top-level** skills: add/rename/remove the
  relative symlink `plugins/<category>/skills/<skill-name>` →
  `../../../skills/<skill-name>`. A router member is a normal skill directory
  under `skills/` but gets no plugin symlink: `build_routers.py` creates
  `skills/<router>/members/<name>` and the generated member table, and the
  category plugin contains only the router. CI enforces this with
  `python3 scripts/check_plugins.py`.
- Fast loop for a docs or plugin change:
  `scripts/check_all.sh --only docs,plugins`; `--list` shows every check name.
- A reference file over 100 lines carries a `## Contents` heading with
  section links within its first 20 lines, so a partial read still shows its
  scope. CI enforces this with `python3 scripts/check_reference_tocs.py`.
- A SKILL.md or reference states no dated facts (ISO dates, "as of 2026",
  "verified 2026-09-07"): they turn false without notice. Dated provenance
  (when a version was verified, a source revision, a re-check deadline) goes
  into one paragraph per file that starts `As of 20YY-MM[-DD]`. Code spans,
  code blocks and URLs are exempt. CI enforces this with
  `python3 scripts/check_dated_claims.py`.
- No Markdown table in `skills/**/*.md` is wider than three columns, fenced
  output templates included, because skills and the answers they shape are
  read on a phone; use a nested list or a table of at most three columns. CI
  enforces this with `python3 scripts/check_table_width.py`.
- Every `references/`, `scripts/`, `assets/`, `evals/` or `members/` path a
  SKILL.md or reference names exists relative to the skill directory, and
  every relative Markdown link exists relative to the linking file — code
  spans and fenced commands included. CI enforces this with
  `python3 scripts/check_skill_paths.py`.
- A GitHub step an agent executes names the operation (list open issues,
  read an issue with comments, create a PR), then uses this canonical
  sentence, keeping the `gh` command as the fallback for agents without the
  GitHub MCP: "Use the GitHub MCP tools if the session has them; otherwise
  `gh` …". GraphQL-backed `gh` porcelain (`gh issue`, `gh pr`, `gh search`,
  `gh label`, `gh repo view`, `gh release list|view`) fails with HTTP 403 in
  Claude Code cloud sessions; REST (`gh api`, `gh run`) works. A script that
  runs headlessly cannot call MCP tools, so it uses `gh api` against the REST
  endpoint. CI enforces this with `python3 scripts/check_gh_graphql.py`.
