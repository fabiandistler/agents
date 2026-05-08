# Agents

Personal agent skills and custom utilities for AI-assisted software
engineering. Designed to be agent-agnostic: works with Claude Code,
Codex CLI, opencode, Continue, Aider, and any agent that can read
Markdown.

See [`AGENTS.md`](AGENTS.md) for the agent-facing entry point and
[`skills.json`](skills.json) for a maschine-readable manifest.

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
| `adr-workflow/` | Skill for Architecture Decision Records |
| `problem-first-explanation/` | Skill for problem-first code explanation |
| `r-package-dev/` | Skill for R package development (data.table, roxygen2, testthat) |
| `skill-creator/` | Skill for authoring and iterating on new skills |
| `software-design/` | Skill for function argument design and API patterns |
| `stepdown-rule/` | Skill for stepdown rule code organisation |
| `eval-suite/` | A/B harness for measuring the effect of skills/MCP/AGENTS.md on agent code generation |
| `mcp-wiki-server/` | MCP server exposing a Wikipedia tool to MCP-aware agents |
| `scripts/` | Repo tooling (manifest generator) |
