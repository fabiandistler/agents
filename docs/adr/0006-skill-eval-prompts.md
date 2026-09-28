# ADR-0006: Per-skill eval prompts live in `skills/<name>/evals.json`

## Status

Accepted (2026-09-27)

## Context

None of the 26 skills ships test scenarios, while Anthropic's skill-authoring
guidance asks for at least three per skill
(https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).
Every per-skill review filed its own P3 "add eval prompts" item, but with no
agreed location or format each would be solved differently. Recall prompts live
in the external eval-suite repo (`eval-suite/recall`), which covers triggering
but not output quality.

## Decision

Every auto and router skill ships `skills/<name>/evals.json` with this schema:

```json
{
  "should_trigger": ["<user utterance 1>", "<user utterance 2>", "<user utterance 3>"],
  "should_not_trigger": ["<near-miss utterance>"],
  "expected_behavior": "<optional free text describing correct behavior>"
}
```

`should_trigger` holds at least three non-empty user utterances that should
trigger the skill; `should_not_trigger` holds at least one near-miss utterance
that must not trigger it; `expected_behavior` is an optional non-empty string
summarizing correct behavior. Command skills (`activation: command`) are exempt:
they are user-invoked, so there is no trigger decision to evaluate.

`scripts/check_evals.py` validates presence and schema for every auto/router
skill from `skills.json` via `catalogue.py`, and is wired into CI.

## Decision drivers

- One location next to the skill keeps prompts under progressive disclosure and
  inside the repo the per-skill issues already belong to; an external-only
  convention would scatter content across repositories.
- The `should_trigger` / `should_not_trigger` split mirrors Anthropic's eval
  structure, so prompts stay portable if they are later executed by a harness.
- JSON is machine-checkable in CI with stdlib only; a Markdown convention would
  need prose parsing for the same gate.
- Command skills have no trigger surface, so requiring prompts there would force
  vacuous content to satisfy the counter.

## Considered options

- **Eval-suite entries only.** Rejected: the suite lives in another repo and
  covers recall, not output quality; every per-skill issue would need a
  cross-repo edit.
- **`references/EVALS.md` in Markdown.** Rejected: unenforceable counts without
  prose parsing, and a second format alongside the JSON the harness will want.
- **Per-prompt `expected_behavior` objects.** Rejected for now: heavier schema
  before any content exists. The top-level string carries the intent; revisit
  when an LLM judge needs per-prompt rubrics.
- **Hard CI gate from day one.** Rejected: no skill ships evals yet, so a
  failing gate would break `main` on merge. The check runs warn-only until
  content lands.

## Consequences

- The per-skill P3 eval issues fill in content against this schema; this ADR is
  their reference and they are not reworded here.
- `check_evals.py` runs in CI warn-only (exit 0 with gaps listed) while no
  skill ships evals. Once coverage lands, CI flips to
  `python scripts/check_evals.py --strict`, which exits non-zero on any gap.
- A skill that legitimately cannot supply three distinct triggers documents why
  in its P3 issue instead of padding the list.

## Notes

Deliberately out of the schema, recorded so it is not helpfully re-added:

- Per-prompt authorship metadata, dates, or difficulty labels.
- Judge rubrics, scores, or pass thresholds; deciding the harness is separate work.
- Aggregate quality gates (averages across skills); presence is the only gate.
