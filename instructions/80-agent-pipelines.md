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
