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
  install paths for Claude Code, Codex CLI, and opencode. See
  `./install.sh --help`.
- `eval-suite/` is an A/B harness for measuring whether a skill
  improves an agent's output. It is not a skill itself.
- `mcp-wiki-server/` is a small MCP server exposing a wiki /
  knowledge-base tool to any MCP-aware agent. It is independent of the
  skills.

## Skill catalogue

| Skill | When to use |
|---|---|
| [adr-workflow](skills/adr-workflow/SKILL.md) | Establishing or maintaining Architecture Decision Records in a repo. |
| [analyze-coupling](skills/analyze-coupling/SKILL.md) | Measuring how coupled or brittle a codebase is — afferent/efferent coupling, Instability, Abstractness, Distance from the Main Sequence, and the Zones of Pain and Uselessness. |
| [architecture-pattern-advisor](skills/architecture-pattern-advisor/SKILL.md) | Choosing or restructuring the architecture of a new or existing repository — system topology (monolith, modular monolith, microservices, serverless, event-driven) and code organization (layered, by-domain, hexagonal, clean/onion). |
| [problem-first-explanation](skills/problem-first-explanation/SKILL.md) | Producing technical explanations that lead with the concrete problem before the abstract solution. |
| [r-package-dev](skills/r-package-dev/SKILL.md) | Designing or refactoring R packages (data.table, roxygen2, testthat). |
| [skill-creator](skills/skill-creator/SKILL.md) | Creating, editing, evaluating, or benchmarking skills in this repo. |
| [software-design](skills/software-design/SKILL.md) | Designing function/module APIs to maximize functionality and minimize interface surface ("deep modules"). |
| [stepdown-rule](skills/stepdown-rule/SKILL.md) | Writing or refactoring functions so the code reads top-down, one level of abstraction per function. |

For agents that auto-load `AGENTS.md` (Codex CLI, opencode, Aider): the
links above are valid relative paths and may be fetched on demand. For
machine consumption prefer `skills.json`.

## Conventions for skill authors

- A skill lives in `skills/<skill-name>/` and has a `SKILL.md` at its root.
- `SKILL.md` starts with YAML frontmatter providing at minimum:
  - `name` — must match the directory name.
  - `description` — single paragraph; the first sentence becomes the
    `summary` in `skills.json`.
- Optional frontmatter fields:
  - `compatibility` — runtime / language requirements in plain prose.
  - `metadata.version` — semver-ish string.
- The body is plain Markdown. Avoid agent-specific vocabulary
  (slash-commands, "the Skill tool", proprietary tool names). Prefer
  describing the workflow in terms any reader can apply.
- After editing any `SKILL.md` frontmatter, regenerate the manifest:
  `python3 scripts/build_manifest.py`. Verify it is in sync before
  committing with `python3 scripts/build_manifest.py --check`.
