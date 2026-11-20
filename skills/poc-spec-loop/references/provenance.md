# Provenance

What was verified when, and what has not run against a real project yet.

As of 2026-11-20, the toolchain versions in [toolchains.md](toolchains.md)
were last verified 2026-09-07, the `az` flags were checked against the
Microsoft Learn reference on 2026-10-12, the `http-service` smoke command
first ran for real on 2026-10-26, and the two claude notes in the `loop.sh`
header were taken from the Claude Code docs on 2026-11-20; re-verify all of
them before each real run.
Sunset: delete this skill on 2027-03-01 if no second real run has happened by
then.

- The `http-service` smoke command in [deploy-targets.md](deploy-targets.md) has run for real once, with Docker 29.9.2 and curl 8.5.0; that run found and fixed the one-character container name and the missing `--retry-all-errors`.
- `assets/loop.sh` has not yet run against a real PoC with any runner; its tests use stub CLIs. Verify the runner's flags first; the script header records which CLI versions they were checked against. The Azure DevOps path (push, `az repos pr create`, `azure-pipelines.yml`) has not run against a real organization either.
- The two claude notes in the `loop.sh` header (live view via the session transcript, `--bare` as the coming `claude -p` default) come from the Claude Code docs (`code.claude.com/docs/en/headless`, `/sessions`); neither has been tried in a loop run. Source: forge pass on aihero.dev, "Here's how to stream Claude Code with AFK Ralph".
