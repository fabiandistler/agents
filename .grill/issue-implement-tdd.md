# `/implement` never actually invokes `/tdd`: 0 invocations across 17 measured runs

## Summary

`implement`'s `SKILL.md` says:

> Use /tdd where possible, at pre-agreed seams.

Measured against a local session corpus, that instruction does not route. Across **17 `/implement` invocations** there were **0 invocations of `/tdd`** — in any spelling, by any path.

This is a report about **routing**, not about output quality. Some of the measured runs produced good, well-tested work. They simply did it without the skill ever being reached.

Note that by `implement`'s own stated success criterion — *"You can see an actual `/tdd` invocation in the trace, not just tests appearing in the diff"* — **0 of 17 runs met it.**

## Evidence

Corpus: 1125 local Claude Code session transcripts (`*.jsonl`).

| Query | Hits |
|---|---|
| `"skill":"…tdd"` (Skill tool invocation) | **0** |
| `<command-name>…tdd…` (slash command) | **0** |
| `/implement` invocations | **17**, across 17 session files |

**Validity probe:** the same query shape finds **413 Skill-tool invocations overall** in the corpus (e.g. `architecture:architecture` 170×, `communication:html-artifacts` 119×, `mattpocock-skills:grilling` 7×, `mattpocock-skills:domain-modeling` 6×). The query is not broken, and sibling skills from this same plugin *do* register — so this is not an artifact of the plugin being newly installed.

**Per-run signature.** One session in the corpus was itself an analysis of this question and is excluded throughout. In **11 of the 17** runs, the words `seam` and `tdd` occur on exactly **2 JSONL lines each**. Direct inspection of one such run (`624869af`) shows why: both words appear **only** in `implement`'s own instruction text and in the available-skills boilerplate listing. Neither word appears anywhere in the actual work.

A counter-check on the runs with the highest counts:

- `71e65915` — every non-boilerplate `tdd` hit is base64 noise inside binary blobs. Zero genuine use.
- `e2730da8` — seams **were** carefully negotiated, in prose, and well (*"One seam. The single test seam is `arch_check(…)` … Deliberately **not** seams: …"*). 59 distinct test files were touched. **`/tdd` still never fired.**

That last run is the one that makes this report honest: the seam discipline and the testing both happened, from the model's general competence rather than from the skill. The defect is that the instruction does not route, not that the results are bad.

## Hypothesised mechanism

Labelled as hypothesis — the measurement above is the fact; this is the explanation I find most plausible for it.

The instruction carries two escape hatches in a single sentence:

1. **"where possible"** licenses skipping outright.
2. **"at pre-agreed seams"** is a precondition that nothing inside `implement` establishes.

`tdd` refuses to write a test at an unconfirmed seam. If no seam was agreed, the faithful reading of the sentence is *"not possible here"* → skip. `implement`'s own documentation already states this plainly:

> The word "pre-agreed" is doing real work, and it is also the skill's weakest joint. Nothing inside `implement` agrees the seams. `tdd` is the skill that asks, and it refuses to write a test at an unconfirmed seam. So in practice the agreement happens either upstream in the spec, or in the first exchange of the run. If it happens nowhere, the precondition never fires and the run quietly becomes "just write the code".

The measurement suggests that in practice it happens nowhere, at a rate of 17 out of 17.

Worth noting what is *not* the cause: `tdd` carries no `disable-model-invocation`, so it is not blocked from being called. It is simply never reached.

## Possible directions

Deliberately not prescriptive — the maintainers know the design constraints better than this report does.

- Have `implement` establish the seams itself as an explicit first beat, rather than delegating a precondition it cannot satisfy.
- Make the seam agreement a **consumed artifact** produced upstream, so the precondition becomes a data dependency rather than an in-run hope.
- Remove or tighten the `where possible` hedge, so skipping requires a stated reason.

## Related

- **#1035** (`/implement-spec` doesn't drive `/tdd`, unlike `/implement`) — adjacent, and relevant in a specific way: that issue rests on the premise *"/implement drives /tdd at pre-agreed seams"*, offered structurally and without measurement. The data above suggests the premise does not hold, which would widen #1035's scope rather than narrow it — both skills would share the same root cause in the unestablished seam precondition.
- **#1060** (Add acceptance locks and hard gates across the planning-to-implementation flow) — same underlying theme of preconditions that are stated but not enforced.

## Limits of this report

- Single user, single machine. 1125 sessions is a reasonable sample of one person's usage, not of the user base.
- Detection is by transcript grep across three spellings (Skill tool, slash command, skill-file read). If `/tdd` can be consumed by a path that leaves none of those three traces, this would under-count — though the 413-invocation validity probe makes a systematic blind spot unlikely.
- Session IDs above are local identifiers, included only so the per-run claims are individually checkable in principle.
