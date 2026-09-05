# Agents

Personal agent skills and custom utilities for AI-assisted software
engineering. Designed to be agent-agnostic: works with Claude Code,
Codex CLI, opencode, Continue, Aider, and any agent that can read
Markdown.

See [`AGENTS.md`](AGENTS.md) for the agent-facing entry point and
[`skills.json`](skills.json) for a machine-readable manifest.

## Install

### As Claude plugins (Claude Code, claude.ai, Claude Desktop, Cowork)

This repo doubles as a Claude plugin marketplace: every skill category is
packaged as one plugin (see `plugins/` and
[`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json)), so
you can install exactly the domains you want. Beyond skills, the
`architecture` plugin ships two read-only analysis subagents
(`coupling-analyst`, `cohesion-analyst`). Skills carry their own reference
catalogs under `references/`, read on demand — no extra runtime needed.

- **Claude Code**:

  ```
  /plugin marketplace add fabiandistler/agents
  /plugin install architecture@fabiandistler-agents
  ```

- **claude.ai / Claude Desktop / Cowork**: Settings → Plugins → Add
  marketplace → GitHub → `fabiandistler/agents`, then install individual
  plugins. Their skills show up in chat via `/` or the `+` menu.

Plugin skills are namespaced (`communication:documentation`). A routed
category registers only its router, so there it is the router that carries
the namespace (`architecture:architecture`). In Claude
Code, use either the plugins **or** the symlink install below — with both
at once every skill appears twice.

### As symlinks (Codex CLI, opencode, or local development)

Symlink the skills into your agent's conventional skill directory:

```sh
./install.sh --target=claude    # ~/.claude/skills/
./install.sh --target=codex     # ~/.codex/skills/
./install.sh --target=opencode  # ~/.config/opencode/skills/
./install.sh --target=all
./install.sh --uninstall --target=all
```

Symlinks pick up local edits immediately, which makes this the better
setup while developing skills in this repo.

For Codex CLI the installer covers the full plugins, not just the
skills. `--target=codex` additionally:

- converts each selected plugin's subagents (`coupling-analyst`,
  `cohesion-analyst`) into [Codex custom
  agents](https://developers.openai.com/codex/subagents) under
  `~/.codex/agents/<name>.toml`. The generated files carry a marker
  comment; files you created yourself are never overwritten, and
  `--uninstall` only removes marker-carrying files. Model and sandbox
  are inherited from your Codex session (the Claude-specific `model:`
  and `tools:` fields have no Codex equivalent).
- disables every nested router member by name in `~/.codex/config.toml`,
  via a marker-delimited `[[skills.config]]` block (`enabled = false`).
  Codex discovers skills recursively and follows symlinks, so without this
  each `members/<name>/SKILL.md` would register as its own skill and the
  router's progressive disclosure would be lost. `--uninstall` removes the
  block.
- installs the user-invoked command skills (`activation: command`) as
  regular skills under `~/.codex/skills/` rather than as Codex custom
  prompts (which are deprecated). Each carries an `agents/openai.yaml`
  sidecar with `policy.allow_implicit_invocation: false`, so Codex only
  runs them on an explicit `$skill-name`, never on its own. The installer
  also removes any leftover `~/.codex/prompts/<name>.md` symlinks a
  previous version created.

Earlier versions also registered a knowledge-base MCP server per plugin.
Those are gone — the skills' `references/` pages are read directly instead.
Both install and `--uninstall` strip whatever an older version left in
`~/.codex/config.toml` and remove its `~/.codex/agents-mcp-runtime` venv.
Any `[mcp_servers.*]` entries you added yourself are untouched.

Restart Codex to pick up the new agents.

### Selecting skills by category

Every skill carries a `category` field in its `SKILL.md` frontmatter —
one of `architecture`, `refactoring`, `ai-ml`,
`workflow`, `communication`, `personal` (the same grouping as the
plugins and the catalogue below). `--category` installs only the chosen
domains:

```sh
./install.sh --target=claude --category=architecture
./install.sh --target=codex  --category=refactoring,workflow
```

### Selecting skills by environment

Each skill is tagged with an `environments` field in its `SKILL.md`
frontmatter — `coding`, `chat`, or both. Use `--env` to install only one
group, so a chat app like Claude Desktop gets your chat skills while a
coding agent gets the coding ones:

```sh
./install.sh --target=claude --env=coding   # only coding skills
./install.sh --target=claude --env=chat      # only chat skills
./install.sh --target=claude --env=all       # everything (default)
```

`--env` defaults to `all`, so omitting it installs every skill as before.
A skill without an `environments` field belongs to every environment.

### Skills that skip an agent

A skill can opt out of individual agents with a `targets` frontmatter field
(a comma-separated subset of `claude`, `codex`, `opencode`; absent means all
of them). `install.sh` never links it for an excluded agent, and removes a
link it created there before. Use it when a runtime already ships an
equivalent of its own. A skill that excludes `claude` also gets no plugin
symlink, since `plugins/` is the Claude distribution of these skills.

The installer also prunes leftovers: a dangling symlink pointing at a skill
this repo no longer ships is removed on the next install or uninstall.
Symlinks that point outside this repo are never touched.

## Contents

| Directory | Description |
|---|---|
| `skills/` | All installable skills — every subdirectory holding a `SKILL.md` is one, grouped below by category |
| `plugins/` | The same skills packaged as Claude plugins, one plugin per category (architecture adds analysis subagents) |
| `eval-suite/` | A/B harness for measuring the effect of skills/MCP/AGENTS.md on agent code generation |
| `mcp-wiki-server/` | Standalone MCP server exposing a wiki / knowledge-base tool to MCP-aware agents. Not used by the plugins |
| `scripts/` | Repo tooling (manifest generator, consistency checks) |

## Skill catalogue

Some categories ship a **router** skill (`activation: router`, named after the
category) as their single registered entry point: a broad-description skill
whose body routes to the specific sub-skill to read before acting. The
sub-skills nest under the router's `members/` directory and load only when
routed to, so the category adds one trigger entry instead of many. The router
body is generated from `skills.json` by `scripts/build_routers.py`. Every
sub-skill is still listed individually below.

### Architecture & design (`architecture`)

| Skill | When to use |
|---|---|
| `skills/adr-workflow/` | Establishing or maintaining Architecture Decision Records in a repo. |
| `skills/architecture-pattern-advisor/` | Choosing or restructuring the architecture of a new or existing repository — system topology (monolith, modular monolith, microservices, serverless, event-driven) and code organization (layered, by-domain, hexagonal, clean/onion). |
| `skills/c4-modeling/` | Drafting a C4 model of a system interactively and rendering it as Mermaid diagrams — System Context, Container, and Component views plus landscape, dynamic, and deployment — per c4model.com best practices. |
| `skills/coupling-cohesion/` | Measuring coupling or cohesion of existing code — a module's cohesion and LCOM, codebase-wide coupling metrics (instability, abstractness, Zones of Pain/Uselessness), or whether one specific dependency is balanced (Khononov strength/distance/volatility). |
| `skills/ddd/` | Domain-Driven Design across strategy and code — subdomain classification, context mapping, choosing an implementation pattern, and the correctness conventions for aggregates, value objects, domain events, and event sourcing. |
| `skills/fitness-functions/` | Designing architecture fitness functions — automated, CI-wired checks (cycle detection, layer rules, metric thresholds, chaos/conformity monitors) that govern architecture characteristics. |
| `skills/logical-component-design/` | Decomposing a new system or feature into named logical components — the iterative Workflow / Actor-Action identification cycle, the Entity-Trap antipattern, cohesion and coupling refinement, and the Law of Demeter. |
| `skills/microservices-design/` | Designing or reviewing how microservices interact — boundaries, coupling, communication style, contract versioning, cross-service code reuse, sagas, and resiliency patterns (timeouts, bulkheads, circuit breakers, retries) — via a distilled Newman ruleset. |
| `skills/sql-schema-design/` | Designing or reviewing a SQL schema, decomposing complex queries, partitioning, or gating CI/CD on schema drift. |

### Refactoring & code quality (`refactoring`)

| Skill | When to use |
|---|---|
| `skills/refactoring/` | Restructuring existing code safely, working through review feedback, building features test-first, and staging risky changes — migrations, cutovers, rollouts — whose blast radius is hard to predict. |

### AI & ML (`ai-ml`)

| Skill | When to use |
|---|---|
| `skills/llm-application-engineering/` | Diagnosing LLM output failures, ordering LLM app architecture builds, defining production monitoring metrics, or applying craft-level conventions for prompting, evaluation/LLM-judges, guardrails, finetuning, and training data. |
| `skills/ml-project-lifecycle/` | Scoping an ML project, picking a model/baseline, handling missing data, or planning pipelines and staged deployment. |

### Workflow & planning (`workflow`)

| Skill | When to use |
|---|---|
| `skills/natural-planning/` | When a project feels stuck, vague, or overwhelming, or a to-do isn't yet a concrete physical next action. |
| `skills/oss-scouting/` | Scouting one third-party open-source repo for issues worth a small contribution — policy gate, repro, root-cause analysis, fix diff, and a submit checklist, written locally for the user to submit themselves. |
| `skills/repo-status/` | Generating a status update from recent activity — standup prep, yesterday/today/blockers, structuring rough notes into a shareable update. |

### Communication & writing (`communication`)

| Skill | When to use |
|---|---|
| `skills/communication-analysis/` | Analyzing or rewriting feedback, messages, or conversations for congruence, hidden appeals, clarity, or boundaries. |
| `skills/documentation/` | Writing or revising technical documentation for a named reader — README, API reference, runbook, architecture doc, or onboarding guide. |
| `skills/html-artifacts/` | Producing a self-contained HTML file instead of a markdown reply when content has spatial, comparative, or interactive structure — comparisons, diagrams, timelines, decks, throwaway editors. |
| `skills/problem-first-explanation/` | Producing technical explanations that lead with the concrete problem before the abstract solution. |
| `skills/stakeholder-update/` | Writing a status update for readers outside the immediate working group — weekly/monthly leadership status, launch announcement, risk escalation, or the same progress retold for partners and customers. |

### Personal & knowledge (`personal`)

| Skill | When to use |
|---|---|
| `skills/hypertrophy-training/` | Experienced trainee: set volume, RIR/effort, auto-regulation, diagnosing a stalled lift, training under elevated injury risk, or returning after an injury (educational). |
