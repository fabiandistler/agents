---
title: Agent pipelines
targets: all
---

## Agent pipelines

- Whoever finds a problem does not grade it. Grading runs as its own step with fresh context.
- Hand the grader the scale verbatim, with anchored levels (what exactly 0, 25, 50, 75 and 100 mean). No paraphrase, no free-form "confidence: high".
- The threshold applies before writing, not after. Anything below it appears nowhere — not even as "uncertain, but worth mentioning".
- Silence is a valid output. Produce a no-findings report only when someone explicitly expects one.
- The false-positive catalogue belongs in the finder prompt, not the grader's. It enumerates what is never reported: pre-existing issues, anything a linter, typechecker or compiler already catches, nitpicks, anything outside the change.
- Split parallel finders by evidence source, not by topic. Two agents on the same source produce correlated errors, not coverage.
- Run classification and grading on the cheap model, the actual analysis on the strong one.
- **Writing into external systems**:
  - Re-check the entry condition immediately before the write, not only at the start. The pipeline runtime sits between the first check and the write, and the state can have changed since.
  - A state file and a re-check cover different failure modes: the file prevents repetition across runs, the re-check catches a state change within a run. Both are needed.
  - If the re-check fails, abort with no side effect and one log line naming the reason.
  - An unattended LLM step never holds a write credential; it emits a patch artifact, a separate model-free step validates and publishes it.
  - Enforce scope outside the prompt: check every changed path against an anchored allowlist, including untracked files (`git ls-files --others --exclude-standard`), and stage only that list.
  - Agent self-edits (prompt, workflow, references) pass the same allowlist and human PR; an edit loosening tools, tokens or permissions is reported, never applied.
- **Handing off work for review (showboat)**:
  - Before handing off a feature or fix, build `demo.md` with `uvx showboat@0.6.1` (every `showboat` below means that; read `--help` first): `note` for intent, `exec` per claim, `pop` failed tries.
  - Never edit `demo.md` directly; only showboat commands write to it.
  - Finish with `showboat verify demo.md`; hand off only on exit 0.
  - R: `exec` runs `<lang> -c`, which Rscript lacks. Use `exec demo.md bash "Rscript -e '…'"`.
  - Keep outputs deterministic (seeds, no timestamps, no live DB) or verify breaks.
  - Never exec against real client or HR data: demo.md is committed verbatim. Never set SHOWBOAT_REMOTE_URL.
  <!-- Source: forge 2026-09-30, simonw/showboat v0.6.1. Review: Todoist "Abbau-Review Showboat-Block" (2027-06-07). -->
