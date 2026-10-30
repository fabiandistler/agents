# ADR-0007: Keep the ai-ml router, measured routed against flat

## Status

Accepted (2026-10-30) — measured: routed 61/70 against flat 45/70, keep the router.
Proposed (2026-09-27) with the prompts and method below.

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

Keep the `ai-ml` router. The seven positive and two negative recall prompts
below and the routed-vs-flat method were recorded first; the measurement under
**Result** decides for routed.

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

## Result

Run 2026-10-30 with `recall/hillclimb_live.py` in eval-suite (commit
5e953f9, flow `.claude/hillclimb/ai-ml-recall`): both arms concurrently on
agents 4c1bd9d, `claude-opus-5-5` served for every session, 21 cases × 5 reps
per arm, 210 sessions, no failed or retried runs. The nine prompts above are
kept verbatim; twelve more were merged in from `live_prompts.json` and the
skills' `evals.json` files.

- Expected member reached: routed 61/70 (87.1%), flat 45/70 (64.3%). The
  23-point gap is about twice the ±12-point noise floor at this n, and close
  to ADR-0002's 28 points for `architecture`.
- Per member: llm-application-engineering 31/35 against 23/35,
  ml-project-lifecycle 30/35 against 22/35.
- Flat beat routed on no case. Routed won 6 of the 14 named-member cases
  (`adr-ship-image` 5/5 against 0/5, `adr-tabular-model` and
  `adr-finetune-rag` 5/5 against 2/5), and the other 8 tied.
- Negatives: 0/25 fires in either arm. No run in either arm reached the wrong
  member; flat misses are sessions that answered without any skill.
- Weak in both arms, so a description problem rather than a layout one:
  `demand-forecast` 0/5 and 0/5, `rag-wrong-docs` 1/5 and 0/5, and the two
  either-member cases 1/10 and 0/10.

Per the method, routed wins, so the router stays as in ADR-0002.

## Consequences

- The router stays as rewritten in #211 with the member first sentences from
  #213, with its Codex disable block and plugin wrapper.
- The eval lives in eval-suite (`.claude/hillclimb/ai-ml-recall`); a change to
  the router or member descriptions can be measured against the same 21
  cases.
- The four prompts weak in both arms are the next target for description
  work, not for the layout.

## Notes

Deliberately not decided here, so it is not helpfully re-litigated:

- Whether two members justify a router on budget grounds alone.
- Whether any prompt above should be reworded before the run.
- Anything about output quality evals — recall only, per ADR-0006 scope split.
