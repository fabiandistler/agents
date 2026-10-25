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

**Skills fire on their description.** Most skills are model-triggered: the
agent reads the one-paragraph `description` in every `SKILL.md` and loads the
body when a request matches. You do not name them.

**Two categories go through a router.** `architecture` and `ai-ml` register a
single broad entry point that routes to the right sub-skill, so the category
costs one trigger entry instead of one per sub-skill. Members live under the
router's `members/` directory and load only when routed to. Ask for the
situation, not for a member: the router loads and reads the member itself. A
member has no registered name of its own, so do not expect `/architecture:ddd`;
on Claude the registered entry is the router.

**Command skills are invoked explicitly.** Skills marked `activation: command`
are user-invoked only and install as commands. In Claude Code they carry the
plugin namespace:

- `/refactoring:improve-codebase`
- `/workflow:oss-scouting`
- `/workflow:poc-spec-loop`
- `/workflow:pypet-snippets`
- `/workflow:release-pr`
- `/workflow:repo-status`
- `/communication:tldr`
- `/communication:was`

OpenCode discovers them as `/name` slash commands from the ordinary skill
directory through `opencode/slash` and `opencode/autoinvoke` metadata. Codex
gets them as skills that run only on an explicit `$name`, such as
`$oss-scouting`. The list above is hand-maintained; `skills.json` records
`activation: command` for each one.

**Shared rules are separate from skills.** Skills are capabilities loaded on
demand. `instructions/` has three tiers: always-on rules, Claude path-scoped
rules, and on-demand rules whose pointers stay in the global instruction file.
`./install.sh --instructions` composes the always-on rules and pointers into
`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` or
`~/.config/opencode/AGENTS.md`, and installs the on-demand files under
`~/.agents/instructions/`. Claude loads path-scoped rules only for matching
files; the installer and this repo's cloud mirror add a Claude hook that
supplies the Python baseline before `uv init`. Content outside the managed
markers is never touched.

**Only the human merges.** A pre-tool hook blocks the agent from merging pull
requests or enabling auto-merge: the `merge-guard` plugin in Claude Code,
`./install.sh --merge-guard` for Codex CLI and opencode. This repo's
`.claude/settings.json` carries the same hook for cloud sessions. Details and limits:
[docs/install.md](docs/install.md#pr-merge-guard---merge-guard).
The `secret-guard` plugin (`--secret-guard`) likewise blocks reading credential
files and dumping the environment:
[docs/install.md](docs/install.md#secret-read-guard---secret-guard).

**Reading without installing.** [`skills.json`](skills.json) is the generated
machine-readable manifest: `scripts/build_manifest.py` writes it from each
`SKILL.md`, so do not edit it by hand. It carries a `version` and a `skills`
array whose entries hold `name`, `category`, `path`, `summary` and
`activation` (`auto` is omitted because it is the default), plus
`compatibility`, `version`, `environments` and `targets` when the skill
declares them. For an ordinary skill the `summary` is the description's first
sentence, truncated at 200 characters; for a router it is the whole
description, with `when_to_use` appended the way Claude does. Query it with
`jq`:

```sh
jq -r '.skills[] | [.category, (.activation // "auto"), .name] | @tsv' skills.json
```

[`AGENTS.md`](AGENTS.md) is the agent-facing entry point with links to every
`SKILL.md`.

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

Skill-authoring conventions — frontmatter fields, description budgets, the
manifest and catalogue that must stay in sync — are in
[`AGENTS.md`](AGENTS.md); the step-by-step checklist is
[`docs/contributing.md`](docs/contributing.md). Before opening a PR, run what
CI runs — `ci.yml` calls the same script, so this is its whole list:

```sh
pip install -r scripts/check_all.requirements.txt  # pinned prek, pytest, pyyaml
scripts/check_all.sh          # one PASS/FAIL/MISSING line per check
scripts/check_all.sh --list   # the checks and the tools each needs
scripts/check_all.sh --only docs,plugins  # the fast loop for a docs or plugin change
```

`--only` and `--skip` omit the other checks entirely; they are not reported as
skipped. The pull-request gates `pr-issue-links` and `maintenance-gate` are
separate workflows, not checks inside `check_all.sh`.

A check whose tool is not installed is reported as `MISSING` and the script
exits 3, so a skipped gate never reads as green. The checks need Python 3.11 or
later (CI uses 3.12); if `python3` on `PATH` is older, point `PYTHON=` at a
newer interpreter. The mermaid check also needs Node.js (`npx`).

The hooks in `.pre-commit-config.yaml` are run by
[prek](https://github.com/j178/prek); they pin ruff, ty, shellcheck, shfmt and
the secret scanner. The shellcheck and shfmt hooks install under Python 3.12,
and the secret scanner builds with the Go on `PATH` (prek downloads a
toolchain only when none is found). Run `prek install` once and they fire on
every commit; `check_all.sh` runs them too, so a skipped hook fails the build
rather than landing on `main`. The same install adds a commit-msg hook that
rejects subjects outside Conventional Commits and a pre-push hook that runs
`check_all.sh` without its prek, mermaid and install-smoke checks (export
`PYTHON=` as above, or the push stops with exit 4).

`build_manifest.py --check` runs first for a reason: the catalogue and plugin
checks read `skills.json`, so a stale manifest makes them answer from stale
metadata.
