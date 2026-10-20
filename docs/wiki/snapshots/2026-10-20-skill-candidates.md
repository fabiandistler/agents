# 2026-10-20 — New-skill candidates

Source: read-only research run on 2026-10-20 (repo issues, catalogue,
web sources dated in the run's report). User chose "propose" (option B).

Ranked by value/effort:
1. **analysis-audit** (workflow, command, M) — verify an R/Python data
   analysis before it is relied on: row counts through each filter/join,
   stated assumptions, a second query for surprising results. No
   data-analysis skill exists; `skills/ai-ml/SKILL.md:7` excludes wrangling.
   Risk: ADR-0003 looks-easy trigger floor.
2. **agent-ready-repo** (workflow, command, M) — make a repo's checks
   runnable in Claude/Codex/opencode cloud sessions. Evidence: this wiki's
   env-gaps and unrunnable-commands pages. Risk: overlaps the built-in
   `session-start-hook` skill; Codex/opencode setup hooks unverified.
3. **unattended-agent-job** (ai-ml router member, M–L) — design scheduled/CI
   agent jobs where the LLM only emits a patch. Evidence:
   `instructions/80-agent-pipelines.md`, #464, #456, #489. Risk: may only
   restate the 80 fragment.
4. **dependency-update** (workflow, command, S) — uv/renv updates under the
   7-day cooldown plus pip-audit. Evidence: #431,
   `instructions/30-python.md`. Risk: Dependabot/Renovate overlap unverified.

Rejected: skill A/B harness (skill-creator covers it), R package dev
(`posit-dev/skills` ships it), MCP / SQL schema / showboat / Azure DevOps
forge rules (already declined: #287, `1a697bd`, #461, `.out-of-scope/`).
