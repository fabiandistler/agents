# Provenance

What was verified when, and what has not run against a real project yet.

- Toolchain versions in [toolchains.md](toolchains.md) were last verified 2026-09-07; re-verify before each real run.
- `assets/loop.sh` has not yet run against a real PoC with any runner; its tests use stub CLIs. Verify the runner's flags first; the script header records which CLI versions they were checked against. The Azure DevOps path (push, `az repos pr create`, `azure-pipelines.yml`) has not run against a real organization either; `az` flags were checked against the Microsoft Learn reference on 2026-10-12.
