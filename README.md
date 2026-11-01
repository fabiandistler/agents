# Agents

Skills for AI coding agents — architecture review, refactoring, LLM
application engineering, planning, and technical writing — written once as
plain Markdown and installed into Claude Code, Codex CLI, or opencode from
one place.

Browse the [interactive skill catalogue](https://fabiandistler.github.io/agents/).

A skill is a Markdown file an agent loads when it recognizes the situation it
describes; the bulk of each one stays in `references/` pages that load only
when they are needed. There is no runtime, no server, and nothing to install
at agent start beyond a symlink or a plugin entry.

What this is **not**: a general-purpose skill marketplace. The catalogue is
personal and opinionated, and skills are prose an agent reads — none of them
execute code on their own.

## Quick start

Two supported paths, one per agent family. Both take under five minutes.

**Claude plugins** (Claude Code, claude.ai, Claude Desktop, Cowork) — the only
way to get the skills, subagents, merge guard and secret read guard into
Claude. Install whole categories, no clone needed. In Claude Code:

```
/plugin marketplace add fabiandistler/agents
/plugin install architecture@fabiandistler-agents
```

Elsewhere: `Customize > Plugins > Add marketplace > GitHub` →
`fabiandistler/agents`, then install individual plugins. Auto-update is off by
default for this marketplace; see
[docs/install.md](docs/install.md#claude-code-plugins-only).

**Symlinks** (Codex CLI, opencode). Requires `bash` and `git`, plus `python3`
for `--update`, the Codex and OpenCode subagents, the guard hooks, and the
Claude `uv init` context hook. For Claude, `install.sh` only syncs the shared
instructions (`--instructions`):

```console
$ git clone https://github.com/fabiandistler/agents.git ~/src/agents
$ cd ~/src/agents
$ ./install.sh --target=opencode
opencode: /home/you/.config/opencode/skills
  linked    /home/you/.config/opencode/skills/ai-ml -> /home/you/src/agents/skills/ai-ml
  linked    /home/you/.config/opencode/skills/architecture -> /home/you/src/agents/skills/architecture
  linked    /home/you/.config/opencode/skills/communication-analysis -> /home/you/src/agents/skills/communication-analysis
  ...
  linked    /home/you/.config/opencode/skills/was -> /home/you/src/agents/skills/was
  updated   /home/you/.config/opencode/agents/cohesion-analyst.md (opencode-agent)
  updated   /home/you/.config/opencode/agents/coupling-analyst.md (opencode-agent)
```

That output is trimmed and illustrative; paths follow your home directory and
the link set follows the current catalogue. The two agent files come from the
`architecture` plugin's read-only analysis subagents.

Start your agent and ask it something the catalogue covers — *"is this
service's structure sound?"* — and it loads `architecture`, which routes to
the sub-skill for the question. Re-running the installer prints `ok` for links
that already exist; `--uninstall` removes every artifact it created, not only
links: generated agent files, managed config blocks, guard hooks and its
saved-state entry go too, while files it does not own stay untouched.

Symlinks pick up local edits immediately, which makes this the better setup
while developing skills here. `--target=codex` does more than link skills —
see [`docs/install.md`](docs/install.md).

## Configuration

`install.sh` flags. `./install.sh --help` is the source of truth; per-agent
behaviour is in [`docs/install.md`](docs/install.md).

| Flag | Default | Effect |
|---|---|---|
| `--target=claude\|codex\|opencode\|all\|detected` | required for installs | Which agent's skill directory to link into (`claude`: none, only `--instructions` plus cleanup of old links; `detected`: every agent whose command or config directory exists). `--update` rejects it; the targetless `--uninstall --git-hook` removes only the Git hooks |
| `--category=<name>[,<name>...]` | all | Restrict to categories: `architecture`, `refactoring`, `ai-ml`, `workflow`, `communication`, `personal` (not Claude: install only some plugins instead) |
| `--env=coding\|chat\|all` | `all` | Restrict by each skill's `environments:` field — coding agent vs chat app (not Claude) |
| `--instructions` | off | Compose always-on rules and pointers, install on-demand files, and add Claude's `uv init` context hook |
| `--merge-guard` | off | Also install the PR merge guard hook (Codex, opencode; Claude uses the `merge-guard` plugin) |
| `--secret-guard` | off | Also install the secret read guard hook (Codex, opencode; Claude uses the `secret-guard` plugin) |
| `--dry-run` | off | Print every action, change nothing |
| `--uninstall` | off | Remove every artifact this installer created for the selected target: links, generated agent files, managed blocks, guard hooks and config. Drop it from the saved state, deleting that file when the selection is empty. Foreign files are never touched |
| `--check` | off | Report drift between the selected install and the managed files; exit 0 clean, 3 drift; writes no managed files, and `--output` writes the report |
| `--output FILE` | — | With `--check`: write the full drift report as TSV |
| `--update` | off | Replay the last successful install (targets, filters, components) from the saved state file; exit 4 when none exists |
| `--git-hook` | off | Install `post-merge`/`post-rewrite` hooks in this clone that run `--update` when `--update --check` finds drift; `--uninstall --git-hook` removes them |

```sh
./install.sh --target=opencode --category=architecture
./install.sh --target=codex    --env=coding
./install.sh --target=all      --instructions --dry-run
```

## Usage

Most skills fire on their `description`: ask for the situation, not the skill.
`architecture` and `ai-ml` each register one router that loads the right
sub-skill. Command skills run only when invoked, such as
`/refactoring:improve-codebase` in Claude Code. [`docs/usage.md`](docs/usage.md)
covers routers, the list of command skills, the shared instructions, the merge
and secret guards, and reading `skills.json` without installing.

## Skill catalogue

Categories marked with a router register only that router; every sub-skill is
still listed here.

### Architecture & design (`architecture`)

| Skill | When to use |
|---|---|
| `skills/architecture-pattern-advisor/` | Choosing or restructuring the architecture of a new or existing repository — system topology (monolith, modular monolith, microservices, serverless, event-driven) and code organization (layered, by-domain, hexagonal, clean/onion). |
| `skills/c4-modeling/` | Drafting a C4 model of a system interactively and rendering it as Mermaid diagrams — System Context, Container, and Component views plus landscape, dynamic, and deployment — per c4model.com best practices. |
| `skills/coupling-cohesion/` | Measuring coupling or cohesion of existing code — a module's cohesion and LCOM, codebase-wide coupling metrics (instability, abstractness, Zones of Pain/Uselessness), or whether one specific dependency is balanced (Khononov strength/distance/volatility). |
| `skills/ddd/` | Domain-Driven Design across strategy and code — subdomain classification, context mapping, choosing an implementation pattern, and the correctness conventions for aggregates, value objects, domain events, and event sourcing. |
| `skills/fitness-functions/` | Designing architecture fitness functions — automated, CI-wired checks (cycle detection, layer rules, metric thresholds, chaos/conformity monitors) that govern architecture characteristics. |
| `skills/logical-component-design/` | Decomposing a new system or feature into named logical components — the iterative Workflow / Actor-Action identification cycle, the Entity-Trap antipattern, cohesion and coupling refinement, and the Law of Demeter. |
| `skills/microservices-design/` | Designing or reviewing how microservices interact — boundaries, coupling, communication style, contract versioning, cross-service code reuse, sagas, and resiliency patterns (timeouts, bulkheads, circuit breakers, retries) — via a distilled Newman ruleset. |

### Refactoring & code quality (`refactoring`)

| Skill | When to use |
|---|---|
| `skills/improve-codebase/` | Reviewing a repository's architecture for deepening opportunities — a visual HTML report of candidates with before/after diagrams and a top recommendation, then a round-by-round interview on the one you pick, keeping the glossary and ADRs current. |
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
| `skills/poc-spec-loop/` | Bring a greenfield R, Python, or bash PoC to production readiness in two gated phases — interactive spec (SPEC.md + prd.json), then a per-task TDD loop with fresh context up to a pull request. |
| `skills/pypet-snippets/` | Curating pypet command snippets — creating, finding, editing, running and aliasing them on request, or proposing one for recurring terminal commands. |
| `skills/release-pr/` | Turning the current branch into a release PR for an R or Python package — confirmed version bump, NEWS.md/CHANGELOG.md, checks, PR body — and, after merge, tagging and publishing the release (GitHub, Azure Repos, GitLab). |
| `skills/repo-status/` | Generating a status update from recent activity — standup prep, yesterday/today/blockers, structuring rough notes into a shareable update. |

### Communication & writing (`communication`)

| Skill | When to use |
|---|---|
| `skills/blue-team/` | Developing a raw early idea — tech decision, project pitch, LinkedIn thesis, personal choice — into a sharper version that holds up before its audience, with load points, reinforcements, and a hardness grade. |
| `skills/communication-analysis/` | Analyzing or rewriting feedback, messages, or conversations for congruence, hidden appeals, clarity, or boundaries. |
| `skills/documentation/` | Writing or revising technical documentation for a named reader — README, API reference, runbook, architecture doc, or onboarding guide. |
| `skills/html-artifacts/` | Producing a self-contained HTML file instead of a markdown reply when content has spatial, comparative, or interactive structure — comparisons, diagrams, timelines, decks, throwaway editors. |
| `skills/ki-stil/` | Checking a German draft for wording that reads generic or AI-typical — counted, located style signals from a bundled scanner, an evidence-tiered verdict, and concrete rewrites; a heuristic, never an authorship verdict. |
| `skills/problem-first-explanation/` | Producing explanations — technical or not — that lead with the concrete problem before the solution. |
| `skills/red-team/` | Attacking a finished or near-finished artefact or decision — ADR, proposal, LinkedIn post, application, career move — through a fresh-context critic, a materiality gate, stakeholder lenses, and a categorical verdict. |
| `skills/stakeholder-update/` | Writing a status update for readers outside the immediate working group — weekly/monthly leadership status, launch announcement, risk escalation, or the same progress retold for partners and customers. |
| `skills/tldr/` | Compressing something too long to read into the few facts needed to decide or act, read instead of the source — the last message and the work behind it, or a named file, PR, document, or thread. |
| `skills/was/` | Re-pitching a short message that was read but not understood, in plain German — the missing context added first instead of shortening, short active sentences, the repo's glossary terms kept verbatim. |

### Personal & knowledge (`personal`)

| Skill | When to use |
|---|---|
| `skills/hypertrophy-training/` | Experienced trainee: set volume, RIR/effort, auto-regulation, diagnosing a stalled lift, training under elevated injury risk, or returning after an injury (educational). |

## Repository layout

| Directory | Description |
|---|---|
| `skills/` | All installable skills — every subdirectory holding a `SKILL.md` is one |
| `instructions/` | Always-on, Claude path-scoped and on-demand rule fragments, composed or installed by `--instructions` |
| `.claude/` | Mixed tree for Claude cloud sessions in this repo: generated skill and agent links, `rules/` files and hook entries; vendored Matt Pocock skills; the repo-owned `repo-error-checker`/`skill-reviewer` agents; hand-written `hooks/` and settings outside the generated entries |
| `.claude-plugin/` | The plugin marketplace manifest (`marketplace.json`) |
| `plugins/` | The same skills packaged as Claude plugins, one per category (architecture adds two read-only analysis subagents), plus the hook-only `merge-guard` and `secret-guard` plugins |
| `scripts/` | Repo tooling: manifest generator, router generator, consistency checks |
| `maintenance/` | Reports from the scheduled maintenance rotation described in [`MAINTENANCE.md`](MAINTENANCE.md) |
| `vendor/` | Lock file and license of code vendored from other repositories: `repo-maintenance/` pins the maintenance scanner in `scripts/` (see [`MAINTENANCE.md`](MAINTENANCE.md)) |
| `docs/` | Documentation beyond this README — start at [`docs/README.md`](docs/README.md) |
| `.github/` | CI workflows (`ci.yml`, `pr-issue-links.yml`, `maintenance-gate.yml`, `claude.yml`) and Dependabot configuration |
| `.out-of-scope/` | Decision archive for mechanisms this repo deliberately does not build |

## Documentation

The map is [`docs/README.md`](docs/README.md). The pages a reader most often
wants directly:

- [`docs/install.md`](docs/install.md) — per-agent install detail, verification, troubleshooting, uninstall
- [`docs/contributing.md`](docs/contributing.md) — end-to-end checklist for adding or changing a skill
- [`GLOSSARY.md`](GLOSSARY.md) — the repo's canonical vocabulary
- [`docs/adr/README.md`](docs/adr/README.md) — index of the architecture decisions

## Contributing

Before opening a PR, run what CI runs: `scripts/check_all.sh` prints one
PASS/FAIL/MISSING line per check, `--list` names them, and `--only docs,plugins`
is the fast loop for a docs or plugin change. The step-by-step checklist is
[`docs/contributing.md`](docs/contributing.md); its
[Run checks](docs/contributing.md#run-checks) section covers the check setup
and the prek hooks. Skill-authoring conventions are in
[`docs/skill-conventions.md`](docs/skill-conventions.md).
