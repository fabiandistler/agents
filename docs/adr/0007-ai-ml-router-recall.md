# ADR-0007: ai-ml router recall prompts and deferred routed-vs-flat measurement

## Status

Proposed (2026-09-27) — prompts and method recorded, measurement open, no keep/drop verdict yet.

## Context

The `ai-ml` category ships two members behind one router entry. With two
members, flat costs about 335 chars against the router's 206 (auto total
4035/10000), so budget savings alone do not justify the extra hop. Only
measured recall can justify the router, as ADR-0002 did for `architecture`
(routed 62/70, 88.6% against flat 42/70, 60.0%).

No live recall prompts for ai-ml exist in `eval-suite/recall` (the
`check_live.py` and `live_prompts.json` added in 9219732 cover architecture
only). That suite lives in the external eval-suite repo, which is out of scope
for this change — no cross-repo writes are attempted here. The prompts and the
measurement method are recorded locally so a later sync can copy them over and
run both arms.

## Decision

Record seven positive and two negative ai-ml recall prompts below, with the
routed-vs-flat method to run once the description rewrite lands. Measurement
itself is an open follow-up. No keep/drop verdict is made here.

Positive prompts (should trigger `ai-ml`):

1. My chatbot keeps making things up — how do I stop the hallucinations.
2. Should we fine-tune the model or add retrieval for this knowledge task.
3. The agent loops and keeps calling the wrong tool — how do I fix tool selection.
4. How do I test prompt changes without breaking what already works.
5. Which model should I use for this tabular classification data.
6. Accuracy dropped after launch — when should we retrain the model.
7. Is this model good enough to ship for image classification.

Negative prompts (must not trigger `ai-ml`):

1. Clean this CSV with pandas and plot the columns.
2. Speed up this numpy loop over the array.

## Method

Run routed and flat arms on the same commit and model, at least five reps per
prompt, arms run concurrently so a degraded moment hits both in the same
window, no `SKILL.md` touched between arms. Report per-prompt counts per batch
and the pooled headline. Negatives must fire zero times. If flat wins, drop
the router along with its Codex disable block and plugin wrapper; if routed
wins, keep the router as in ADR-0002.

## Consequences

- The recall set above is the input to the future measurement; it does not
  itself decide routed against flat.
- The external eval-suite sync (`live_prompts.json`, `check_live.py` runs) is a
  separate follow-up in the other repo, not part of this change.
- Until the numbers exist, the router stays as rewritten in #211 with the
  member first sentences from #213.

## Notes

Deliberately not decided here, so it is not helpfully re-litigated:

- Whether two members justify a router on budget grounds alone.
- Whether any prompt above should be reworded before the run.
- Anything about output quality evals — recall only, per ADR-0006 scope split.
