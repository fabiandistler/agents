# Agents

Skills for AI coding agents — architecture review, refactoring, LLM
application engineering, planning, and technical writing — written once as
plain Markdown and installed into Claude Code, Codex CLI, or opencode from
one place.

A skill is a Markdown file an agent loads when it recognizes the situation it
describes; the bulk of each one stays in `references/` pages that load only
when they are needed. There is no runtime, no server, and nothing to install
at agent start beyond a symlink or a plugin entry.

What this is **not**: a general-purpose skill marketplace. The catalogue is
personal and opinionated, and skills are prose an agent reads — none of them
execute code on their own.

## Quick start

Two supported paths. Both take under five minutes; pick one — running both in
Claude Code makes every skill appear twice.

**Claude plugins** (Claude Code, claude.ai, Claude Desktop, Cowork) — install
whole categories, no clone needed. In Claude Code:

```
/plugin marketplace add fabiandistler/agents
/plugin install architecture@fabiandistler-agents
```

Elsewhere: Settings → Plugins → Add marketplace → GitHub →
`fabiandistler/agents`, then install individual plugins.

**Symlinks** (Codex CLI, opencode, or local development on this repo).
Requires `bash` and `git`; `python3` only for the Codex extras:

```console
$ git clone https://github.com/fabiandistler/agents.git ~/src/agents
$ cd ~/src/agents
$ ./install.sh --target=claude
claude: /home/you/.claude/skills
  linked    /home/you/.claude/skills/architecture -> /home/you/src/agents/skills/architecture
  linked    /home/you/.claude/skills/documentation -> /home/you/src/agents/skills/documentation
  linked    /home/you/.claude/skills/refactoring -> /home/you/src/agents/skills/refactoring
  ...
  linked    /home/you/.claude/commands/repo-status.md -> /home/you/src/agents/skills/repo-status/SKILL.md
```

Start your agent and ask it something the catalogue covers — *"is this
service's structure sound?"* — and it loads `architecture`, which routes to
the sub-skill for the question. Re-running the installer prints `ok` for links
that already exist; `--uninstall` removes exactly the links it created.

Symlinks pick up local edits immediately, which makes this the better setup
while developing skills here. `--target=codex` does more than link skills —
see [`docs/install.md`](docs/install.md).

## Configuration

`install.sh` flags. `./install.sh --help` is the source of truth; per-agent
behaviour is in [`docs/install.md`](docs/install.md).

| Flag | Default | Effect |
|---|---|---|
| `--target=claude\|codex\|opencode\|all` | *required* | Which agent's skill directory to link into |
| `--category=<name>[,<name>...]` | all | Restrict to categories: `architecture`, `refactoring`, `ai-ml`, `workflow`, `communication`, `personal` |
| `--env=coding\|chat\|all` | `all` | Restrict by each skill's `environments:` field — coding agent vs chat app |
| `--instructions` | off | Also compose `instructions/` into the agent's global instruction file |
| `--dry-run` | off | Print every action, change nothing |
| `--uninstall` | off | Remove only the links and managed blocks this installer created |

```sh
./install.sh --target=claude --category=architecture
./install.sh --target=codex  --env=coding
./install.sh --target=all    --instructions --dry-run
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
are user-invoked only and install as commands — `/oss-scouting`,
`/repo-status` in Claude Code.

**Shared rules are separate from skills.** Skills are capabilities loaded on
demand; rules that apply to *every* session live in `instructions/` as
single-topic fragments, composed into `~/.claude/CLAUDE.md` or
`~/.codex/AGENTS.md` by `./install.sh --instructions`. Content outside the
managed markers is never touched.

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

## Repository layout

| Directory | Description |
|---|---|
| `skills/` | All installable skills — every subdirectory holding a `SKILL.md` is one |
| `instructions/` | Always-on rule fragments, composed into the agent's global instruction file by `--instructions` |
| `plugins/` | The same skills packaged as Claude plugins, one per category (architecture adds two read-only analysis subagents) |
| `scripts/` | Repo tooling: manifest generator, router generator, consistency checks |
| `eval-suite/` | A/B harness for measuring the effect of skills / MCP / AGENTS.md on agent output |
| `mcp-wiki-server/` | Standalone MCP server exposing a wiki tool. Not used by the plugins |
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
shellcheck -S warning install.sh scripts/*.sh eval-suite/run.sh
bash scripts/test_install.sh                # install.sh smoke test in a temp HOME
```

The hooks in `.pre-commit-config.yaml` are run by
[prek](https://github.com/j178/prek) (`uv tool install prek`). Run `prek
install` once and they fire on every commit; CI runs them too, so a skipped
hook fails the build rather than landing on `main`. `eval-suite/tasks/` is
exempt from the whitespace hooks — those `prompt:` blocks reproduce real user
prompts byte for byte.

`build_manifest.py --check` runs first for a reason: the catalogue and plugin
checks read `skills.json`, so a stale manifest makes them answer from stale
metadata.
