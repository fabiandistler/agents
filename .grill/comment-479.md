Your diagnosis — "nothing in the skill ever agrees any seams, so the trigger for TDD never fires by construction" — matches what a measurement over my local transcripts shows. Posting the numbers in case a measured rate is more useful than another anecdote.

**Corpus:** 1125 local Claude Code session transcripts, single user, single machine.

| Query | Hits |
| --- | --- |
| `/implement` invocations | 17, across 17 sessions |
| `/tdd` invocations, any spelling (Skill tool, slash command) | **0** |
| Skill-tool invocations overall (validity probe) | 413 |

The validity probe matters: the same query shape finds 413 skill invocations across the corpus, and sibling skills from the same plugin register normally, so this is not a broken query or a newly installed plugin. By `implement`'s own stated success criterion — "You can see an actual `/tdd` invocation in the trace" — 0 of 17 runs met it.

Within those runs, the split tracks the **handover**, not the skill:

| What was passed to `/implement` | Runs | Seam work in the transcript |
| --- | --- | --- |
| A bare issue number (`15`, `142`, `18`, …) | 12 | none, in all twelve |
| `yes` / empty | 3 | none |
| A sentence referring to written issues | 2 | substantial |

Session size does not explain it: three bare-number sessions of 1.1–1.3 MB show no seam work, while the two that do are prose invocations.

One counter-check worth having, because it cuts against the "output is bad" reading: the single run with genuine seam work argued its seams explicitly in prose and touched 59 test files — good work — and still never invoked `/tdd`. It had read GitHub issues whose bodies were `to-spec` specs, carrying the spec template's `## Testing Decisions` section with a seam definition in it.

That last point suggests tightening `implement`'s wording may not be sufficient on its own: when the input is a ticket rather than a spec, there are no seams in it to work from, because `to-tickets` has no seam field in either template. I filed that half separately as #1078.

**Limits:** one user, one machine, 17 runs. The handover correlation is a correlation, not a causal proof.

---

Unrelated to the report: thank you for these skills. I have been using them for about four weeks now, both at work and on personal projects, and they have held up well. A report like this one only exists because the set is worth leaning on hard enough for its edges to matter.
