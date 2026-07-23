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
  it also registers the plugins' knowledge-base MCP servers in
  `~/.codex/config.toml` and converts the plugins' subagents to Codex
  custom agents in `~/.codex/agents/` (both marker-delimited, removed
  by `--uninstall`). See `./install.sh --help`.
- `plugins/` packages the same skills as Claude plugins, one plugin per
  category (each bundles its skills via symlinks into `skills/`).
  `.claude-plugin/marketplace.json` makes the repo installable as a
  plugin marketplace in Claude Code, claude.ai, Claude Desktop, and
  Cowork. The `architecture` plugin additionally ships two read-only
  analysis subagents (`coupling-analyst`, `cohesion-analyst`), and the
  `architecture` and `refactoring` plugins each embed a knowledge-base
  MCP server (a reuse of `mcp-wiki-server/` over each skill's
  `references/`, wired up via `kb/` symlinks and a plugin `.mcp.json`;
  requires `uv` at runtime).
- `eval-suite/` is an A/B harness for measuring whether a skill
  improves an agent's output. It is not a skill itself.
- `mcp-wiki-server/` is a small MCP server exposing a wiki /
  knowledge-base tool to any MCP-aware agent. It works standalone, and
  is also embedded by the `architecture` and `refactoring` plugins to
  serve their skills' reference catalogs.

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

### Architecture & design (`architecture`)

Registered through the [`architecture`](skills/architecture/SKILL.md) router.

| Skill | When to use |
|---|---|
| [adr-workflow](skills/adr-workflow/SKILL.md) | Establishing or maintaining Architecture Decision Records in a repo. |
| [architecture-pattern-advisor](skills/architecture-pattern-advisor/SKILL.md) | Choosing or restructuring the architecture of a new or existing repository — system topology (monolith, modular monolith, microservices, serverless, event-driven) and code organization (layered, by-domain, hexagonal, clean/onion). |
| [c4-modeling](skills/c4-modeling/SKILL.md) | Drafting a C4 model of a system interactively and rendering it as Mermaid diagrams — System Context, Container, and Component views plus landscape, dynamic, and deployment — per c4model.com best practices. |
| [codebase-design](skills/codebase-design/SKILL.md) | Shared vocabulary and workflow for designing deep modules. |
| [coupling-cohesion](skills/coupling-cohesion/SKILL.md) | Measuring coupling or cohesion of existing code — a module's cohesion and LCOM, codebase-wide coupling metrics (instability, abstractness, Zones of Pain/Uselessness), or whether one specific dependency is balanced (Khononov strength/distance/volatility). |
| [ddd](skills/ddd/SKILL.md) | Domain-Driven Design across strategy and code — subdomain classification, context mapping, choosing an implementation pattern, and the correctness conventions for aggregates, value objects, domain events, and event sourcing. |
| [fitness-functions](skills/fitness-functions/SKILL.md) | Designing architecture fitness functions — automated, CI-wired checks (cycle detection, layer rules, metric thresholds, chaos/conformity monitors) that govern architecture characteristics. |
| [logical-component-design](skills/logical-component-design/SKILL.md) | Decomposing a new system or feature into named logical components — the iterative Workflow / Actor-Action identification cycle, the Entity-Trap antipattern, cohesion and coupling refinement, and the Law of Demeter. |
| [microservices-design](skills/microservices-design/SKILL.md) | Designing or reviewing how microservices interact — boundaries, coupling, communication style, contract versioning, cross-service code reuse, sagas, and resiliency patterns (timeouts, bulkheads, circuit breakers, retries) — via a distilled Newman ruleset. |
| [sql-schema-design](skills/sql-schema-design/SKILL.md) | Designing or reviewing a SQL schema, decomposing complex queries, partitioning, or gating CI/CD on schema drift. |

### Refactoring & code quality (`refactoring`)

| Skill | When to use |
|---|---|
| [refactoring](skills/refactoring/SKILL.md) | Deciding whether, when, and how safely to refactor a spotted code smell, then naming the right Fowler technique and applying its step-by-step mechanics. |
| [stepdown-rule](skills/stepdown-rule/SKILL.md) | Writing or refactoring functions so the code reads top-down, one level of abstraction per function. |
| [tdd](skills/tdd/SKILL.md) | Test-driven development. |
| [uncertainty-management](skills/uncertainty-management/SKILL.md) | Facing a risky change whose full impact can't be foreseen: migrations, refactors, deployments, staged rollouts. |

### R development (`r-development`)

| Skill | When to use |
|---|---|
| [r-error-constructors](skills/r-error-constructors/SKILL.md) | Recurring R error (3+ sites): build a stop_* constructor with class hierarchy, conditionMessage(), and class-based tests. |
| [r-package-dev](skills/r-package-dev/SKILL.md) | Building or refactoring R package internals — package-private state and persistence, loading/attaching, lifecycle hooks and deprecation, interface-focused testing. |

### AI & ML (`ai-ml`)

| Skill | When to use |
|---|---|
| [llm-application-engineering](skills/llm-application-engineering/SKILL.md) | Diagnosing LLM output failures, ordering LLM app architecture builds, defining production monitoring metrics, or applying craft-level conventions for prompting, evaluation/LLM-judges, guardrails, finetuning, and training data. |
| [ml-project-lifecycle](skills/ml-project-lifecycle/SKILL.md) | Scoping an ML project, picking a model/baseline, handling missing data, or planning pipelines and staged deployment. |

### Workflow & planning (`workflow`)

| Skill | When to use |
|---|---|
| [grilling](skills/grilling/SKILL.md) | Interview the user relentlessly about a plan or design. |
| [guideline-distillation](skills/guideline-distillation/SKILL.md) | Distilling a style guide, ADR, RFC, wiki, or linter config into a lean project rules file for coding agents. |
| [handoff](skills/handoff/SKILL.md) | Compact the current conversation into a handoff document for another agent to pick up. |
| [natural-planning](skills/natural-planning/SKILL.md) | When a project feels stuck, vague, or overwhelming, or a to-do isn't yet a concrete physical next action. |
| [prototype](skills/prototype/SKILL.md) | Build a throwaway prototype to flesh out a design — a runnable terminal app for state/business-logic questions, or several radically different UI variations toggleable from one route. |
| [repo-status](skills/repo-status/SKILL.md) | Generating a status update from recent activity — standup prep, yesterday/today/blockers, structuring rough notes into a shareable update. |
| [skill-creator](skills/skill-creator/SKILL.md) | Creating, editing, evaluating, or benchmarking skills in this repo. |
| [to-issues](skills/to-issues/SKILL.md) | Break a plan, spec, or PRD into independently-grabbable issues on the project issue tracker using tracer-bullet vertical slices. |

### Communication & writing (`communication`)

| Skill | When to use |
|---|---|
| [communication-analysis](skills/communication-analysis/SKILL.md) | Analyzing or rewriting feedback, messages, or conversations for congruence, hidden appeals, clarity, or boundaries. |
| [problem-first-explanation](skills/problem-first-explanation/SKILL.md) | Producing technical explanations that lead with the concrete problem before the abstract solution. |
| [stakeholder-update](skills/stakeholder-update/SKILL.md) | Generating a stakeholder update tailored to audience and cadence — weekly/monthly status, launch announcement, risk escalation, exec/engineering/customer versions. |

### Personal & knowledge (`personal`)

| Skill | When to use |
|---|---|
| [hypertrophy-training](skills/hypertrophy-training/SKILL.md) | Experienced trainee: set volume, RIR/effort, auto-regulation, or diagnosing a stalled lift (educational). |
| [worry-management](skills/worry-management/SKILL.md) | When someone brings a specific worry and explicitly wants help analyzing or resolving it (not a therapy substitute). |
| [zettelkasten-value-hierarchy](skills/zettelkasten-value-hierarchy/SKILL.md) | Classifying or promoting notes by value, or synthesizing higher-value systems/workflows from low-value notes. |

For agents that auto-load `AGENTS.md` (Codex CLI, opencode, Aider): the
links above are valid relative paths and may be fetched on demand. For
machine consumption prefer `skills.json`.

## Conventions for skill authors

- A skill lives in `skills/<skill-name>/` and has a `SKILL.md` at its root.
- `SKILL.md` starts with YAML frontmatter providing at minimum:
  - `name` — must match the directory name.
  - `category` — one of `architecture`, `refactoring`, `r-development`,
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
    budget. `command` skills are user-invoked only: `install.sh` routes them
    to each target's command directory (`~/.claude/commands`,
    `~/.codex/prompts`, `~/.config/opencode/command`) as `<name>.md` instead
    of the skills directory, keeping them out of the auto-trigger metadata.
    For Claude, pair it with `disable-model-invocation: true` in the same
    frontmatter (the runtime realization Claude honors; ignored elsewhere).
  - `compatibility` — runtime / language requirements in plain prose.
  - `environments` — comma-separated list of the environments the skill
    belongs to: `coding`, `chat`, or both (e.g. `environments: coding, chat`).
    `install.sh --env=coding|chat` uses this to install only the matching
    subset. A skill without the field belongs to every environment.
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
