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

## Contents

| Directory | Description |
|---|---|
| `skills/` | All installable skills (each subdirectory has a `SKILL.md`) |
| `skills/adr-workflow/` | Skill for Architecture Decision Records |
| `skills/architecture-pattern-advisor/` | Skill for architecture pattern selection (topology + code organization) and incremental migration |
| `skills/problem-first-explanation/` | Skill for problem-first code explanation |
| `skills/r-package-dev/` | Skill for R package development (data.table, roxygen2, testthat) |
| `skills/skill-creator/` | Skill for authoring and iterating on new skills |
| `skills/software-design/` | Skill for function argument design and API patterns |
| `skills/stepdown-rule/` | Skill for stepdown rule code organization |
| `eval-suite/` | A/B harness for measuring the effect of skills/MCP/AGENTS.md on agent code generation |
| `mcp-wiki-server/` | MCP server exposing a wiki / knowledge-base tool to MCP-aware agents |
| `scripts/` | Repo tooling (manifest generator) |
