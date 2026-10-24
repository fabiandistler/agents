# Agent pipeline conventions

Use these rules when a pipeline separates finding, grading, and publishing. They apply to unattended LLM pipelines and to independent meta-grading of code-review findings.

## Finding and grading

- Whoever finds a problem does not grade it. Grading runs as a separate step with fresh context.
- For application failure modes, give each mode its own binary pass/fail judge. Do not use a continuous score for these application judges.
- An independent meta-grader evaluating code-review findings uses this anchored scale, not the application pass/fail rule:

  | Grade | Meaning |
  |---:|---|
  | 0 | The finding is demonstrably invalid: the changed code or specification directly disproves it, or it is pre-existing. |
  | 25 | The finding is probably invalid: some evidence argues against it, and the defect link is not established. |
  | 50 | The evidence is unresolved: it neither establishes nor disproves that the changed code violates the specification. |
  | 75 | The finding is probably valid: changed behavior and the specification support it, with one material alternative still possible. |
  | 100 | The finding is proven: the changed code and specification or a deterministic reproduction establish the defect, with no reasonable alternative. |

- Give the grader this scale verbatim. Apply the configured threshold before writing; omit every finding below it, including findings described as uncertain.
- Silence is a valid output. Produce a no-findings report only when someone explicitly expects one.
- Put the false-positive catalogue in the finder prompt, not the grader prompt. It names findings that must never be reported: pre-existing issues, anything a linter, typechecker or compiler catches, nitpicks, and anything outside the change.
- Split parallel finders by evidence source, not topic. Two agents inspecting the same source produce correlated errors, not broader coverage.
- Run classification and grading on the cheap model, the actual analysis on the strong one.
- Strip HTML comments, CSS-hidden text, zero-width characters, and embedded Base64 blobs from untrusted text before it reaches a prompt. This narrows injection exposure; a model's output on that text is a recommendation, never the decision.

## External writes

- Before each external write, consult persistent state to prevent repetition across runs and re-check the current entry condition. These cover different failure modes. If the re-check fails, abort without a side effect and log one line naming the reason.
- An unattended LLM step never holds a write credential. It emits a patch artifact; a separate model-free step validates and publishes it.
- Enforce scope outside the prompt: check every changed path against an anchored allowlist, including untracked files (`git ls-files --others --exclude-standard`), and stage only that list.
- Agent self-edits (prompts, workflows, references) pass the same allowlist and human PR. Report edits that loosen tools, tokens, or permissions; do not apply them.
