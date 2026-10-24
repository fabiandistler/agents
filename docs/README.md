# Documentation

Map of this repository's documentation. The [README](../README.md) is the
product page; this page routes from a job to the page that does it.

## Use it

- [Install](install.md) — per-agent paths, verification, troubleshooting, uninstall
- [Skill catalogue](../README.md#skill-catalogue) — every skill and when it fires
- [`skills.json`](../skills.json) — generated manifest; query it instead of crawling `skills/`
- [Glossary](../GLOSSARY.md) — the repo's canonical vocabulary

## Develop it

- [Contributing](contributing.md) — end-to-end checklist for adding or changing a skill
- [Agent conventions](../AGENTS.md) — frontmatter, description budgets, generated files, checks
- [Checks and CI gates](../README.md#contributing) — `scripts/check_all.sh` and the prek hooks
- [Install internals](maintainers/install-internals.md) — Claude cloud mirror, vendored skills, regeneration order
- [Weekly skill audit](agents/skill-audit.md) — the scheduled content review and its checklist

## Reference and records

- [ADR index](adr/README.md) — decisions, status, and rationale
- [Maintenance](../MAINTENANCE.md) — the scheduled code-maintenance rotation
- [Evals](evals/improve-codebase-ab.md) — experiment record for the `improve-codebase` fork
- [Wiki](wiki/index.md) — dated session history; not current guidance
- [Out of scope](../.out-of-scope/) — decision archive for mechanisms this repo does not build
