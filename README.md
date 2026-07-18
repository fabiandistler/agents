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
(`coupling-analyst`, `cohesion-analyst`), and the `architecture` and
`refactoring` plugins each embed a knowledge-base MCP server built on
[`mcp-wiki-server/`](mcp-wiki-server/) that serves their reference
catalogs as lookup tools (requires [`uv`](https://docs.astral.sh/uv/)).

- **Claude Code**:

  ```
  /plugin marketplace add fabiandistler/agents
  /plugin install architecture@fabiandistler-agents
  ```

- **claude.ai / Claude Desktop / Cowork**: Settings → Plugins → Add
  marketplace → GitHub → `fabiandistler/agents`, then install individual
  plugins. Their skills show up in chat via `/` or the `+` menu.

Plugin skills are namespaced (`architecture:adr-workflow`). In Claude
Code, use either the plugins **or** the symlink install below — with both
at once every skill appears twice.

### As symlinks (Codex CLI, opencode, or local development)

Symlink the skills into your agent's conventional skill directory:

```sh
./install.sh --target=claude    # ~/.claude/skills/
./install.sh --target=codex     # ~/.codex/skills/
./install.sh --target=opencode  # ~/.config/opencode/agent/
./install.sh --target=all
./install.sh --uninstall --target=all
```

Symlinks pick up local edits immediately, which makes this the better
setup while developing skills in this repo.

For Codex CLI the installer covers the full plugins, not just the
skills. `--target=codex` additionally:

- registers each selected plugin's knowledge-base MCP server
  (`architecture-kb`, `refactoring-kb`) in `~/.codex/config.toml`,
  inside clearly marked blocks that `--uninstall` removes again.
  Existing `[mcp_servers.*]` entries you added yourself are never
  touched. Like under Claude, the servers need
  [`uv`](https://docs.astral.sh/uv/) at runtime.
- converts each selected plugin's subagents (`coupling-analyst`,
  `cohesion-analyst`) into [Codex custom
  agents](https://developers.openai.com/codex/subagents) under
  `~/.codex/agents/<name>.toml`. The generated files carry a marker
  comment; files you created yourself are never overwritten, and
  `--uninstall` only removes marker-carrying files. Model and sandbox
  are inherited from your Codex session (the Claude-specific `model:`
  and `tools:` fields have no Codex equivalent).

Restart Codex (or run `codex mcp list`) to pick up the new servers and
agents.

### Selecting skills by category

Every skill carries a `category` field in its `SKILL.md` frontmatter —
one of `architecture`, `refactoring`, `r-development`, `ai-ml`,
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

## Contents

| Directory | Description |
|---|---|
| `skills/` | All installable skills (each subdirectory has a `SKILL.md`), grouped below by category |
| `plugins/` | The same skills packaged as Claude plugins, one plugin per category (architecture adds analysis subagents; architecture and refactoring embed a knowledge-base MCP server) |
| `eval-suite/` | A/B harness for measuring the effect of skills/MCP/AGENTS.md on agent code generation |
| `mcp-wiki-server/` | MCP server exposing a wiki / knowledge-base tool to MCP-aware agents; also embedded by the architecture and refactoring plugins |
| `scripts/` | Repo tooling (manifest generator, consistency checks) |

## Skill catalogue

### Architecture & design (`architecture`)

| Skill | When to use |
|---|---|
| `skills/adr-workflow/` | Establishing or maintaining Architecture Decision Records in a repo. |
| `skills/analyze-cohesion/` | Analyzing whether a class, module, file, or package is cohesive — classify it on the best-to-worst cohesion scale, compute LCOM, and recommend a split/merge/leave. |
| `skills/analyze-coupling/` | Measuring how coupled or brittle a codebase is — afferent/efferent coupling, Instability, Abstractness, Distance from the Main Sequence, and the Zones of Pain and Uselessness. |
| `skills/architecture-pattern-advisor/` | Choosing or restructuring the architecture of a new or existing repository — system topology (monolith, modular monolith, microservices, serverless, event-driven) and code organization (layered, by-domain, hexagonal, clean/onion). |
| `skills/balanced-coupling/` | Weighing a specific dependency along Khononov's Balanced Coupling model — integration strength (intrusive/functional/model/contract), distance, and volatility — flagging knowledge leaks and recommending how to rebalance them. |
| `skills/c4-modeling/` | Drafting a C4 model of a system interactively and rendering it as Mermaid diagrams — System Context, Container, and Component views plus landscape, dynamic, and deployment — per c4model.com best practices. |
| `skills/codebase-design/` | Shared vocabulary and workflow for designing deep modules. |
| `skills/ddd-advisor/` | Subdomain classification, buy-vs-build, bounded-context integration, or choosing a DDD implementation pattern. |
| `skills/ddd-conventions/` | Implementation-time DDD correctness rules — aggregates (one per transaction, optimistic concurrency), value objects, past-tense domain events, outbox-pattern publishing, event-sourcing mechanics, and bounded-context integration conventions. |
| `skills/fitness-functions/` | Designing architecture fitness functions — automated, CI-wired checks (cycle detection, layer rules, metric thresholds, chaos/conformity monitors) that govern architecture characteristics. |
| `skills/logical-component-design/` | Decomposing a new system or feature into named logical components — the iterative Workflow / Actor-Action identification cycle, the Entity-Trap antipattern, cohesion and coupling refinement, and the Law of Demeter. |
| `skills/sql-schema-design/` | Designing or reviewing a SQL schema, decomposing complex queries, partitioning, or gating CI/CD on schema drift. |

### Refactoring & code quality (`refactoring`)

| Skill | When to use |
|---|---|
| `skills/fowler-refactoring-catalog/` | Naming the right Fowler refactoring for a code smell and getting its step-by-step mechanics. |
| `skills/refactoring-checklist/` | Deciding whether and when a spotted code smell is worth refactoring now, and how to do it safely in small steps. |
| `skills/stepdown-rule/` | Writing or refactoring functions so the code reads top-down, one level of abstraction per function. |
| `skills/tdd/` | Test-driven development. |
| `skills/uncertainty-management/` | Facing a risky change whose full impact can't be foreseen: migrations, refactors, deployments, staged rollouts. |

### R development (`r-development`)

| Skill | When to use |
|---|---|
| `skills/r-error-constructors/` | Recurring R error (3+ sites): build a stop_* constructor with class hierarchy, conditionMessage(), and class-based tests. |
| `skills/r-package-dev/` | Designing or refactoring R packages (data.table, roxygen2, testthat). |

### AI & ML (`ai-ml`)

| Skill | When to use |
|---|---|
| `skills/llm-application-engineering/` | Diagnosing LLM output failures, ordering LLM app architecture builds, or defining production monitoring metrics. |
| `skills/ml-project-lifecycle/` | Scoping an ML project, picking a model/baseline, handling missing data, or planning pipelines and staged deployment. |

### Workflow & planning (`workflow`)

| Skill | When to use |
|---|---|
| `skills/grilling/` | Interview the user relentlessly about a plan or design. |
| `skills/guideline-distillation/` | Distilling a style guide, ADR, RFC, wiki, or linter config into a lean project rules file for coding agents. |
| `skills/handoff/` | Compact the current conversation into a handoff document for another agent to pick up. |
| `skills/natural-planning/` | When a project feels stuck, vague, or overwhelming, or a to-do isn't yet a concrete physical next action. |
| `skills/prototype/` | Build a throwaway prototype to flesh out a design — a runnable terminal app for state/business-logic questions, or several radically different UI var… |
| `skills/repo-status/` | Generating a status update from recent activity — standup prep, yesterday/today/blockers, structuring rough notes into a shareable update. |
| `skills/skill-creator/` | Creating, editing, evaluating, or benchmarking skills in this repo. |
| `skills/to-issues/` | Break a plan, spec, or PRD into independently-grabbable issues on the project issue tracker using tracer-bullet vertical slices. |

### Communication & writing (`communication`)

| Skill | When to use |
|---|---|
| `skills/communication-analysis/` | Analyzing or rewriting feedback, messages, or conversations for congruence, hidden appeals, clarity, or boundaries. |
| `skills/problem-first-explanation/` | Producing technical explanations that lead with the concrete problem before the abstract solution. |
| `skills/stakeholder-update/` | Generating a stakeholder update tailored to audience and cadence — weekly/monthly status, launch announcement, risk escalation, exec/engineering/customer versions. |

### Personal & knowledge (`personal`)

| Skill | When to use |
|---|---|
| `skills/hypertrophy-training/` | Experienced trainee: set volume, RIR/effort, auto-regulation, or diagnosing a stalled lift (educational). |
| `skills/worry-management/` | When someone brings a specific worry and explicitly wants help analyzing or resolving it (not a therapy substitute). |
| `skills/zettelkasten-value-hierarchy/` | Classifying or promoting notes by value, or synthesizing higher-value systems/workflows from low-value notes. |
