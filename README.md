# Agents

Personal agent skills and custom utilities for AI-assisted software
engineering. Designed to be agent-agnostic: works with Claude Code,
Codex CLI, opencode, Continue, Aider, and any agent that can read
Markdown.

See [`AGENTS.md`](AGENTS.md) for the agent-facing entry point and
[`skills.json`](skills.json) for a machine-readable manifest.

## Install

Symlink the skills into your agent's conventional skill directory:

```sh
./install.sh --target=claude    # ~/.claude/skills/
./install.sh --target=codex     # ~/.codex/skills/
./install.sh --target=opencode  # ~/.config/opencode/agent/
./install.sh --target=all
./install.sh --uninstall --target=all
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
| `skills/` | All installable skills (each subdirectory has a `SKILL.md`) |
| `skills/adr-workflow/` | Establishing or maintaining Architecture Decision Records in a repo. |
| `skills/analyze-cohesion/` | Analyzing whether a class, module, file, or package is cohesive — classify it on the best-to-worst cohesion scale, compute LCOM, and recommend a split/merge/leave. |
| `skills/analyze-coupling/` | Measuring how coupled or brittle a codebase is — afferent/efferent coupling, Instability, Abstractness, Distance from the Main Sequence, and the Zones of Pain and Uselessness. |
| `skills/architecture-pattern-advisor/` | Choosing or restructuring the architecture of a new or existing repository — system topology (monolith, modular monolith, microservices, serverless, event-driven) and code organization (layered, by-domain, hexagonal, clean/onion). |
| `skills/codebase-design/` | Shared vocabulary and workflow for designing deep modules. |
| `skills/communication-analysis/` | Analyzing or rewriting feedback, messages, or conversations for congruence, hidden appeals, clarity, or boundaries. |
| `skills/ddd-advisor/` | Subdomain classification, buy-vs-build, bounded-context integration, or choosing a DDD implementation pattern. |
| `skills/fowler-refactoring-catalog/` | Naming the right Fowler refactoring for a code smell and getting its step-by-step mechanics. |
| `skills/grilling/` | Interview the user relentlessly about a plan or design. |
| `skills/guideline-distillation/` | Distilling a style guide, ADR, RFC, wiki, or linter config into a lean project rules file for coding agents. |
| `skills/handoff/` | Compact the current conversation into a handoff document for another agent to pick up. |
| `skills/hypertrophy-training/` | Experienced trainee: set volume, RIR/effort, auto-regulation, or diagnosing a stalled lift (educational). |
| `skills/llm-application-engineering/` | Diagnosing LLM output failures, ordering LLM app architecture builds, or defining production monitoring metrics. |
| `skills/logical-component-design/` | Decomposing a new system or feature into named logical components — the iterative Workflow / Actor-Action identification cycle, the Entity-Trap antipattern, cohesion and coupling refinement, and the Law of Demeter. |
| `skills/ml-project-lifecycle/` | Scoping an ML project, picking a model/baseline, handling missing data, or planning pipelines and staged deployment. |
| `skills/natural-planning/` | When a project feels stuck, vague, or overwhelming, or a to-do isn't yet a concrete physical next action. |
| `skills/problem-first-explanation/` | Producing technical explanations that lead with the concrete problem before the abstract solution. |
| `skills/prototype/` | Build a throwaway prototype to flesh out a design — a runnable terminal app for state/business-logic questions, or several radically different UI var… |
| `skills/r-error-constructors/` | Recurring R error (3+ sites): build a stop_* constructor with class hierarchy, conditionMessage(), and class-based tests. |
| `skills/r-package-dev/` | Designing or refactoring R packages (data.table, roxygen2, testthat). |
| `skills/refactoring-checklist/` | Deciding whether and when a spotted code smell is worth refactoring now, and how to do it safely in small steps. |
| `skills/repo-status/` | Generating a status update from recent activity — standup prep, yesterday/today/blockers, structuring rough notes into a shareable update. |
| `skills/skill-creator/` | Creating, editing, evaluating, or benchmarking skills in this repo. |
| `skills/sql-schema-design/` | Designing or reviewing a SQL schema, decomposing complex queries, partitioning, or gating CI/CD on schema drift. |
| `skills/stakeholder-update/` | Generating a stakeholder update tailored to audience and cadence — weekly/monthly status, launch announcement, risk escalation, exec/engineering/customer versions. |
| `skills/stepdown-rule/` | Writing or refactoring functions so the code reads top-down, one level of abstraction per function. |
| `skills/tdd/` | Test-driven development. |
| `skills/to-issues/` | Break a plan, spec, or PRD into independently-grabbable issues on the project issue tracker using tracer-bullet vertical slices. |
| `skills/uncertainty-management/` | Facing a risky change whose full impact can't be foreseen: migrations, refactors, deployments, staged rollouts. |
| `skills/worry-management/` | When someone brings a specific worry and explicitly wants help analyzing or resolving it (not a therapy substitute). |
| `skills/zettelkasten-value-hierarchy/` | Classifying or promoting notes by value, or synthesizing higher-value systems/workflows from low-value notes. |
| `eval-suite/` | A/B harness for measuring the effect of skills/MCP/AGENTS.md on agent code generation |
| `mcp-wiki-server/` | MCP server exposing a wiki / knowledge-base tool to MCP-aware agents |
| `scripts/` | Repo tooling (manifest generator) |
