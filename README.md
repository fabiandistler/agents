# Agents

Skills for AI coding agents — architecture review, refactoring, LLM
application engineering, planning, and technical writing — written once as
plain Markdown and delivered to Claude Code, Codex CLI, and opencode from
one place.

A skill is a Markdown file an agent loads when it recognizes the situation it
describes; the bulk of each one stays in `references/` pages that load only
when they are needed. There is no runtime, no server, and nothing to install
at agent start beyond a plugin entry or a path in a config file.

What this is **not**: a general-purpose skill marketplace. The catalogue is
personal and opinionated, and skills are prose an agent reads — none of them
execute code on their own.

## Quick start

Each agent gets the skills through exactly one channel, chosen for how it
refreshes ([ADR-0004](docs/adr/0004-distribution-channels-per-surface.md)).
Running two channels on one agent makes every skill appear twice.

| Surface | Skills come from | Refresh |
|---|---|---|
| Claude Code | marketplace plugin | automatic |
| Codex CLI | marketplace plugin, git source | `codex plugin marketplace upgrade` |
| opencode | skill path pointing at a clone | `git pull` |

**Claude Code** (also claude.ai, Claude Desktop, Cowork) — install whole
categories, no clone needed:

```
/plugin marketplace add fabiandistler/agents
/plugin install architecture@fabiandistler-agents
```

Elsewhere: Settings → Plugins → Add marketplace → GitHub →
`fabiandistler/agents`, then install individual plugins.

**Codex CLI** reads the same marketplace from its git URL:

```sh
codex plugin marketplace add https://github.com/fabiandistler/agents.git
```

**opencode** points a skill path at a clone (`git clone
https://github.com/fabiandistler/agents.git ~/src/agents`, then
`~/src/agents/skills` in its config — the key differs by version, see
[`docs/install.md`](docs/install.md)).

Start your agent and ask it something the catalogue covers — *"is this
service's structure sound?"* — and it loads `architecture`, which routes to
the sub-skill for the question.

## Configuration

Skills are only half of it. `install.sh`, run from a clone, writes what no
plugin format can carry: the shared rules into each agent's global
instruction file, and for Codex the config block that keeps router members
hidden plus the two subagents. It links no skills. Requires `bash`;
`python3` only for the Codex subagents.

```console
$ ./install.sh --target=all
claude:
  updated   /home/you/.claude/CLAUDE.md (9 instruction fragments)
codex:
  agent     cohesion-analyst -> /home/you/.codex/agents/cohesion-analyst.toml
  agent     coupling-analyst -> /home/you/.codex/agents/coupling-analyst.toml
  skills    11 routed members disabled in /home/you/.codex/config.toml
  updated   /home/you/.codex/AGENTS.md (9 instruction fragments)
opencode:
  note      instructions: opencode reads them from /home/you/.claude/CLAUDE.md (nothing to write)
```

Re-running prints `ok` for what is already in place; `--uninstall` strips
exactly what it wrote. Both also remove the skill symlinks an earlier version
of the installer created, so upgrading a machine is one run.
`./install.sh --help` is the source of truth; per-agent behaviour is in
[`docs/install.md`](docs/install.md).

| Flag | Default | Effect |
|---|---|---|
| `--target=claude\|codex\|opencode\|all` | *required* | Which agent's instruction file and config to write |
| `--category=<name>[,<name>...]` | all | Which plugins' Codex extras to write (`architecture`, `refactoring`, `ai-ml`, `workflow`, `communication`, `personal`); codex targets only |
| `--dry-run` | off | Print every action, change nothing |
| `--uninstall` | off | Remove only the managed blocks and files this installer created |

```sh
./install.sh --target=all --dry-run
./install.sh --target=codex --category=architecture,ai-ml
```

## Usage

**Skills fire on their description.** Most skills are model-triggered: the
agent reads the one-paragraph `description` in every `SKILL.md` and loads the
body when a request matches. You do not name them.

**Two categories go through a router.** `architecture` and `ai-ml` register a
single broad entry point that routes to the right sub-skill, so the category
costs one trigger entry instead of one per sub-skill. Members live under the
router's
`members/` directory and load only when routed to.

**Some skills are invoked explicitly.** Skills marked `activation: command`
are user-invoked only — `/workflow:oss-scouting`, `/workflow:repo-status` in
Claude Code, `$repo-status` in Codex.

**Shared rules are separate from skills.** Skills are capabilities loaded on
demand; rules that apply to *every* session live in `instructions/` as
single-topic fragments, composed into `~/.claude/CLAUDE.md` or
`~/.codex/AGENTS.md` by `./install.sh`. Content outside the managed markers
is never touched.

**Reading without installing:** [`skills.json`](skills.json) is the
machine-readable manifest, and [`AGENTS.md`](AGENTS.md) is the agent-facing
entry point with links to every `SKILL.md`.

## Skill catalogue

Categories marked with a router register only that router; every sub-skill is
still listed here.

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
| `skills/refactoring/` | Finding where to start refactoring in a codebase nobody knows well — ranking files by git churn, reading the hotspots, and keeping restructuring separate from behavior change. |

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
| `skills/pypet-snippets/` | Curating pypet command snippets — creating, finding, editing, running and aliasing them on request, or proposing one for recurring terminal commands. |
| `skills/release-pr/` | Turning the current branch into a release PR for an R or Python package — confirmed version bump, NEWS.md/CHANGELOG.md, checks, PR body — and, after merge, tagging and publishing the GitHub release. |
| `skills/repo-status/` | Generating a status update from recent activity — standup prep, yesterday/today/blockers, structuring rough notes into a shareable update. |

### Communication & writing (`communication`)

| Skill | When to use |
|---|---|
| `skills/communication-analysis/` | Analyzing or rewriting feedback, messages, or conversations for congruence, hidden appeals, clarity, or boundaries. |
| `skills/documentation/` | Writing or revising technical documentation for a named reader — README, API reference, runbook, architecture doc, or onboarding guide. |
| `skills/html-artifacts/` | Producing a self-contained HTML file instead of a markdown reply when content has spatial, comparative, or interactive structure — comparisons, diagrams, timelines, decks, throwaway editors. |
| `skills/problem-first-explanation/` | Producing technical explanations that lead with the concrete problem before the abstract solution. |
| `skills/stakeholder-update/` | Writing a status update for readers outside the immediate working group — weekly/monthly leadership status, launch announcement, risk escalation, or the same progress retold for partners and customers. |
| `skills/tldr/` | Compressing something long into the few facts needed to decide or act — the last message and the work behind it, or a named file, PR, document, or thread. |

### Personal & knowledge (`personal`)

| Skill | When to use |
|---|---|
| `skills/hypertrophy-training/` | Experienced trainee: set volume, RIR/effort, auto-regulation, diagnosing a stalled lift, training under elevated injury risk, or returning after an injury (educational). |

## Repository layout

| Directory | Description |
|---|---|
| `skills/` | All installable skills — every subdirectory holding a `SKILL.md` is one |
| `instructions/` | Always-on rule fragments, composed into the agent's global instruction file by `install.sh` |
| `plugins/` | The same skills packaged as plugins, one per category, served to Claude and Codex through the marketplace (architecture adds two read-only analysis subagents) |
| `scripts/` | Repo tooling: manifest generator, router generator, consistency checks |
| `roomba/` | Reports from the scheduled maintenance rotation described in [`ROOMBA.md`](ROOMBA.md) |
| `docs/adr/` | Architecture Decision Records for this repo's own structure |

## Contributing

Skill-authoring conventions — frontmatter fields, description budgets, the
manifest and catalogue that must stay in sync — are in
[`AGENTS.md`](AGENTS.md). Before opening a PR, run what CI runs
(`.github/workflows/ci.yml`):

```sh
python3 scripts/build_manifest.py --check   # skills.json matches the SKILL.md files
python3 scripts/build_routers.py --check    # router bodies match the manifest
python3 scripts/check_descriptions.py       # description budget
python3 scripts/check_docs.py               # catalogue tables in README + AGENTS agree
python3 scripts/check_plugins.py            # plugin symlinks and marketplace entries
python3 scripts/check_instructions.py       # instruction fragments valid
ruff check .
prek run --all-files                        # whitespace, YAML/TOML and ruff hooks
shellcheck -S warning install.sh scripts/*.sh
bash scripts/test_install.sh                # install.sh smoke test in a temp HOME
```

The hooks in `.pre-commit-config.yaml` are run by
[prek](https://github.com/j178/prek) (`uv tool install prek`). Run `prek
 install` once and they fire on every commit; CI runs them too, so a skipped
 hook fails the build rather than landing on `main`.

`build_manifest.py --check` runs first for a reason: the catalogue and plugin
checks read `skills.json`, so a stale manifest makes them answer from stale
metadata.
