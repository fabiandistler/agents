# Agents

This repository is a catalogue of skills and small utilities for AI coding
agents. It targets any agent that can read Markdown instructions — Claude
Code, Codex CLI, opencode, Continue, Aider, Cursor, and others.

## How to use this repo

- Each directory under `skills/` that contains a `SKILL.md` file is a
  self-contained skill.
- `skills.json` (repo root) is the machine-readable manifest of all
  skills. Read it once to discover what is available without crawling the
  tree.
- `install.sh` (repo root) symlinks the skills into the conventional
  install paths for Claude Code, Codex CLI, and opencode. For Codex CLI
  it also converts the plugins' subagents to Codex custom agents in
  `~/.codex/agents/` and disables routed members via a marker-delimited
  block in `~/.codex/config.toml` (both removed by `--uninstall`). See
  `./install.sh --help`.
- `plugins/` packages the same skills as Claude plugins, one plugin per
  category (each bundles its skills via symlinks into `skills/`).
  `.claude-plugin/marketplace.json` makes the repo installable as a
  plugin marketplace in Claude Code, claude.ai, Claude Desktop, and
  Cowork. The `architecture` plugin additionally ships two read-only
  analysis subagents (`coupling-analyst`, `cohesion-analyst`).
- Reference material stays inside the skill that owns it, under
  `skills/<skill>/references/`. SKILL.md names the pages it has; an agent
  opens one only when it needs it. There is no lookup service in front of
  them — plain progressive disclosure is the whole mechanism.
- `eval-suite/` is an A/B harness for measuring whether a skill
  improves an agent's output. It is not a skill itself.
- `mcp-wiki-server/` is a small standalone MCP server exposing a wiki /
  knowledge-base tool to any MCP-aware agent. Nothing else in this repo
  depends on it.

## Skill catalogue

Each skill carries a `category` frontmatter field; the sections below
group the catalogue by those categories.

Some categories ship a **router** skill (`activation: router`, named after
the category) as their single registered entry point. Its description is
deliberately broad, and its body routes to the specific sub-skill to read
before acting; the sub-skills nest under the router's `members/` directory
and load only when routed to (progressive disclosure), so the category adds
one trigger entry instead of many. The router's SKILL.md member table is
generated from `skills.json` by `scripts/build_routers.py` (CI checks it for
drift). The tables below still list every sub-skill individually.

Claude registers only top-level skills, so the members stay hidden there. Codex
discovers skills recursively and follows symlinks
([openai/codex#22275](https://github.com/openai/codex/issues/22275)), so it
would otherwise register each nested `members/<name>/SKILL.md` as its own skill;
`install.sh --target=codex` therefore disables every nested member by name in
`~/.codex/config.toml` (a managed `[[skills.config]]` block, `enabled = false`),
dropping them from the model's skill list. `--uninstall` removes the block.

### Architecture & design (`architecture`)

Registered through the [`architecture`](skills/architecture/SKILL.md) router.

| Skill | When to use |
|---|---|
| [adr-workflow](skills/adr-workflow/SKILL.md) | Establishing or maintaining Architecture Decision Records in a repo. |
| [architecture-pattern-advisor](skills/architecture-pattern-advisor/SKILL.md) | Choosing or restructuring the architecture of a new or existing repository — system topology (monolith, modular monolith, microservices, serverless, event-driven) and code organization (layered, by-domain, hexagonal, clean/onion). |
| [c4-modeling](skills/c4-modeling/SKILL.md) | Drafting a C4 model of a system interactively and rendering it as Mermaid diagrams — System Context, Container, and Component views plus landscape, dynamic, and deployment — per c4model.com best practices. |
| [coupling-cohesion](skills/coupling-cohesion/SKILL.md) | Measuring coupling or cohesion of existing code — a module's cohesion and LCOM, codebase-wide coupling metrics (instability, abstractness, Zones of Pain/Uselessness), or whether one specific dependency is balanced (Khononov strength/distance/volatility). |
| [ddd](skills/ddd/SKILL.md) | Domain-Driven Design across strategy and code — subdomain classification, context mapping, choosing an implementation pattern, and the correctness conventions for aggregates, value objects, domain events, and event sourcing. |
| [fitness-functions](skills/fitness-functions/SKILL.md) | Designing architecture fitness functions — automated, CI-wired checks (cycle detection, layer rules, metric thresholds, chaos/conformity monitors) that govern architecture characteristics. |
| [logical-component-design](skills/logical-component-design/SKILL.md) | Decomposing a new system or feature into named logical components — the iterative Workflow / Actor-Action identification cycle, the Entity-Trap antipattern, cohesion and coupling refinement, and the Law of Demeter. |
| [microservices-design](skills/microservices-design/SKILL.md) | Designing or reviewing how microservices interact — boundaries, coupling, communication style, contract versioning, cross-service code reuse, sagas, and resiliency patterns (timeouts, bulkheads, circuit breakers, retries) — via a distilled Newman ruleset. |
| [sql-schema-design](skills/sql-schema-design/SKILL.md) | Designing or reviewing a SQL schema, decomposing complex queries, partitioning, or gating CI/CD on schema drift. |

### Refactoring & code quality (`refactoring`)

| Skill | When to use |
|---|---|
| [refactoring](skills/refactoring/SKILL.md) | Restructuring existing code safely, working through review feedback, building features test-first, and staging risky changes — migrations, cutovers, rollouts — whose blast radius is hard to predict. |

### AI & ML (`ai-ml`)

| Skill | When to use |
|---|---|
| [llm-application-engineering](skills/llm-application-engineering/SKILL.md) | Diagnosing LLM output failures, ordering LLM app architecture builds, defining production monitoring metrics, or applying craft-level conventions for prompting, evaluation/LLM-judges, guardrails, finetuning, and training data. |
| [ml-project-lifecycle](skills/ml-project-lifecycle/SKILL.md) | Scoping an ML project, picking a model/baseline, handling missing data, or planning pipelines and staged deployment. |

### Workflow & planning (`workflow`)

| Skill | When to use |
|---|---|
| [natural-planning](skills/natural-planning/SKILL.md) | When a project feels stuck, vague, or overwhelming, or a to-do isn't yet a concrete physical next action. |
| [oss-scouting](skills/oss-scouting/SKILL.md) | Scouting one third-party open-source repo for issues worth a small contribution — policy gate, repro, root-cause analysis, fix diff, and a submit checklist, written locally for the user to submit themselves. |
| [repo-status](skills/repo-status/SKILL.md) | Generating a status update from recent activity — standup prep, yesterday/today/blockers, structuring rough notes into a shareable update. |

### Communication & writing (`communication`)

| Skill | When to use |
|---|---|
| [communication-analysis](skills/communication-analysis/SKILL.md) | Analyzing or rewriting feedback, messages, or conversations for congruence, hidden appeals, clarity, or boundaries. |
| [documentation](skills/documentation/SKILL.md) | Writing or revising technical documentation for a named reader — README, API reference, runbook, architecture doc, or onboarding guide. |
| [html-artifacts](skills/html-artifacts/SKILL.md) | Producing a self-contained HTML file instead of a markdown reply when content has spatial, comparative, or interactive structure — comparisons, diagrams, timelines, decks, throwaway editors. |
| [problem-first-explanation](skills/problem-first-explanation/SKILL.md) | Producing technical explanations that lead with the concrete problem before the abstract solution. |
| [stakeholder-update](skills/stakeholder-update/SKILL.md) | Generating a stakeholder update tailored to audience and cadence — weekly/monthly status, launch announcement, risk escalation, exec/engineering/customer versions. |

### Personal & knowledge (`personal`)

| Skill | When to use |
|---|---|
| [hypertrophy-training](skills/hypertrophy-training/SKILL.md) | Experienced trainee: set volume, RIR/effort, auto-regulation, diagnosing a stalled lift, training under elevated injury risk, or returning after an injury (educational). |

For agents that auto-load `AGENTS.md` (Codex CLI, opencode, Aider): the
links above are valid relative paths and may be fetched on demand. For
machine consumption prefer `skills.json`.

## Conventions for skill authors

- A skill lives in `skills/<skill-name>/` and has a `SKILL.md` at its root.
- `SKILL.md` starts with YAML frontmatter providing at minimum:
  - `name` — must match the directory name.
  - `category` — one of `architecture`, `refactoring`,
    `ai-ml`, `workflow`, `communication`, `personal` (the fixed list in
    `scripts/build_manifest.py`). Determines the catalogue section, the
    `install.sh --category` subset, and which plugin bundles the skill.
  - `description` — single paragraph; the first sentence becomes the
    `summary` in `skills.json`. Keep it within the description budget:
    **≤250 chars** for most skills, **≤400 chars** for the small allowlist
    of high-traffic skills in `scripts/check_descriptions.py`. Descriptions
    are always-loaded metadata that competes for a tight context budget
    (Codex CLI truncates the skill list past ~2% of context), so move
    trigger lists and feature enumerations into the SKILL.md **body** (a
    leading `## When to use` section) rather than the frontmatter. CI
    enforces this with `python3 scripts/check_descriptions.py`, which also
    caps the aggregate across all `auto` skills.
- Optional frontmatter fields:
  - `activation` — `auto` (default) or `command`. `auto` skills are
    model-triggered and their description counts toward the auto-trigger
    budget. `command` skills are user-invoked only: for Claude and opencode
    `install.sh` routes them to the target's command directory
    (`~/.claude/commands`, `~/.config/opencode/command`) as `<name>.md`
    instead of the skills directory, keeping them out of the auto-trigger
    metadata. Codex custom prompts are deprecated, so under codex they install
    into `~/.codex/skills/` like any skill, gated by an `agents/openai.yaml`
    sidecar (`policy.allow_implicit_invocation: false`) that keeps Codex from
    auto-triggering them. For Claude, pair `command` with
    `disable-model-invocation: true` in the same frontmatter (the runtime
    realization Claude honors; ignored elsewhere).
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
- The body is plain Markdown. Avoid agent-specific vocabulary
  (slash-commands, "the Skill tool", proprietary tool names). Prefer
  describing the workflow in terms any reader can apply.
- After editing any `SKILL.md` frontmatter, regenerate the manifest:
  `python3 scripts/build_manifest.py`. Verify it is in sync before
  committing with `python3 scripts/build_manifest.py --check`.
- After adding, renaming, or removing a skill, update both catalogue
  tables by hand — `README.md` and `AGENTS.md` (`## Skill catalogue`) —
  keeping their text identical and each skill under the section matching
  its `category`. CI enforces this with `python3 scripts/check_docs.py`.
- Also keep the skill's plugin in sync: add/rename/remove the relative
  symlink `plugins/<category>/skills/<skill-name>` →
  `../../../skills/<skill-name>`. CI enforces this with
  `python3 scripts/check_plugins.py`.

## Agent skills

### Issue tracker

Issues live as GitHub issues on fabiandistler/agents, managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles use their default label strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
