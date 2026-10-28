# A/B: `improve-codebase` fork vs. Pocock's original

> Experiment record, not current guidance. Current instructions: `skills/improve-codebase/`.

The merge gate for spec [#492](https://github.com/fabiandistler/agents/issues/492),
ticket [#497](https://github.com/fabiandistler/agents/issues/497), recorded per
[ADR-0008](../adr/0008-fork-improve-codebase.md): one run of the original and
one of the fork on each of two real repositories, compared on candidates, top
recommendation and evidence.

**Verdict: adjust, then merge.** The fork changed the top recommendation on
lintr and removed every unevidenced finding on both repos. The adjustments the
runs called for are in the commit "improve-codebase: adjust scope, Mode C
mapping and report step from the A/B runs" (refs #497, #496).

## Contents

- [Setup](#setup)
- [escoRAG (Python)](#escorag-python)
- [lintr (R)](#lintr-r)
- [The R LCOM heuristic](#the-r-lcom-heuristic)
- [Friction and what changed](#friction-and-what-changed)
- [Limits](#limits)

## Setup

To reproduce, run each command once per target and stop before the interview.

- **Original:** mattpocock/skills at `49dd158` (v1.3.1),
  `improve-codebase-architecture` plus the `codebase-design` skill it reads.
- **Fork:** this repo at `7215bc8`, `skills/improve-codebase`.
- **Targets:** `fabiandistler/escoRAG` at `bb1e073` (Python, 136 commits, 25
  days old; exact LCOM) and `fabiandistler/lintr` at `2df1a7b` (R, 1139
  commits since 2022-03-15; heuristic LCOM).
- **Model:** `claude-opus-5-5` for all four runs.
- **Mode:** unattended subagent runs, report only. Each run stopped after
  writing the HTML report, before the interview; the user decided this, so the
  interview, glossary/ADR and fitness-function steps were not exercised.
- **No nested subagents** were available, so both commands explored inline and
  the fork took its inline-script fallback (`churn.py`, `lcom.py`,
  `balance_check.py` run directly). The fork's analyst-subagent path
  (`cohesion-analyst`, `coupling-analyst`) was **not** exercised.

Evidence counts below are findings with `path:line` or a metric value / findings
without either.

## escoRAG (Python)

Candidate sets: the same three areas, in the same order.

- Original: "Deepen the Skill index" (Strong) / fork: "Deepen the skill index"
  (Strong)
- Original: "Let the Container build the ingestion path too" (Worth exploring)
  / fork: "Build ingestion through the composition root" (Worth exploring)
- Original: "One LLM-stage module for extract and link" (Speculative) / fork:
  "One module for asking the chat model" (Speculative)

Top recommendation: **same**, deepen the Skill index.

Evidence: original **25 with / 1 without**, fork **27 with / 0 without**. The
original's unevidenced finding was "no ADR-0004 contradiction".

What kind of evidence differs: the original cited `path:line`, size and
hand-counted churn. The fork added co-change counts (`ports.py` with
`qdrant_store.py` 3x, with `container.py` 3x), LCOM (`HybridRetriever`
LCOM=0, `qdrant_store` groups=3 LCOM=13), and Mode C verdicts (graph to
`HybridRetriever` low cohesion, IMBALANCED). It also dropped `cli.py`
(LCOM=11) and `Container` (LCOM=9) as "leave". The default churn ranking was
dominated by `plans/prd.json`; the agent re-ran with `--include 'src/**'` on
its own.

## lintr (R)

Candidate sets: **different**. Two areas overlap, the rest differ.

- Original: "Deepen Source expression parsing: return conditions, stop writing
  into the caller's frame" (Strong) / fork: "Make the parse step return its
  condition instead of writing the caller's locals" (Worth exploring)
- Original: "Collapse the lint cache into one deep module" (Strong) / fork: no
  separate candidate; `cache.R` appears only as evidence inside candidate 1
- Original: "Normalize Exclusions once, at the seam where they enter" / fork:
  `exclude.R` folded into candidate 1
- Original: "Let the Lints collection own its root path" (Speculative) / fork:
  no counterpart
- Original: no counterpart / fork: "Deepen the lint run around one resolved
  settings value" (Strong)
- Original: no counterpart / fork: "Route plain XPath linters through the
  existing deep linter factory" (Speculative)

Top recommendation: **different**. The original picked the parse step that
writes `e`/`w` into the caller's frame. The fork picked the lint run's
package-global `settings` state, and ranked the original's top as its #2.

Evidence: original **27 with / 2 without**, fork **23 with / 0 without**.

What kind of evidence differs: the fork backed its top candidate with git
history, not just code: a settings-ordering bug fixed and reverted
(`500a38c` #2805; `b548c78`, reverted in `dc7a612`, refixed in `a26331b`
#2863), co-change counts (`lint.R` with `settings.R` 11x, `exclude.R` 8x,
`utils.R` 14x) and a churn score (`lint.R` commits=36, score=1.00). Its XPath
candidate rests on bulk commits (`c6320c2` 108 files, `39f7a59` 66, `538440d`
70) and call counts. The original, in turn, found a real bug the fork folded
away: inline code gets a fresh random tempfile cache key every run, so its
cache never hits (`R/cache.R`). The fork's run saw `cache.R` only as a reader
of `settings`.

## The R LCOM heuristic

Misled:

- One-line function bodies bleed into the next function.
- Long signatures parse as signature-only (`lint.R` groups=6, really about 3).
- Handler closures count as functions.
- Package-global `settings` defined in `zzz.R` is invisible to it.
- `--json` does not list group members, so the agent wrote its own helper.

Helped:

- `get_source_expressions.R` groups=1 stopped a split proposal.
- `utils.R` groups=18 flagged a grab-bag (left as "leave").

Mode C inside one R package reported every edge "balanced", which left open
whether that drops a finding.

## Friction and what changed

Changed in the adjustment commit (`skills/improve-codebase/` only):

- **Mode C "high cohesion" mapped to "not a finding".** On escoRAG that would
  have dropped the top candidate's evidence: high cohesion between two
  separate modules *is* the deepening finding. It now supports merging them
  behind one interface; a "balanced" verdict inside one package neither
  confirms nor kills a finding that `path:line` evidence carries.
- **Non-code churn.** `plans/prd.json`, `uv.lock`, `NEWS.md` and `man/`
  flooded the ranking and co-change lists. Scope now passes the source
  directories as `--include` and drops changelogs, generated docs, lock files
  and plan files from co-change lists.
- **Flat ranking and young repos** had a discount rule but no alternative.
  Scope now widens to full history, then falls back to size and the user's
  direction.
- **Bulk commits**: noise for ranking, but evidence for a candidate (lintr's
  XPath sweep). One line now says so.
- **Headless runs** had no fallback for `xdg-open`. The report step now
  prints the path.
- **R LCOM limits** were not stated. The explore step now says a group count
  from it needs a read of the code.

Out of scope here, follow-ups:

- `lcom.py` flags `typing.Protocol` classes (`coupling-cohesion`).
- `lcom.py --json` lacks group members (`coupling-cohesion`).
- `cohesion-analyst` uses `${CLAUDE_PLUGIN_ROOT}`, which does not resolve
  outside a plugin install (`plugins/architecture/agents`).
- The analyst-subagent path is untested; no run could spawn subagents.

Not changed: unpinned CDN scripts without SRI in the report scaffold (kept
for fidelity to upstream).

## Limits

- **n=1 per cell.** One run per command per repo; LLM runs are
  nondeterministic, so a second run could reorder candidates.
- **The baseline also ranked churn by hand** (`git log --name-only | uniq -c`
  on both repos), so the scope difference is smaller than the spec assumed.
  The fork's gain is the co-change, cohesion and balance evidence and the
  absence of unevidenced findings, not the existence of a churn ranking.
- **Steps after the report were not run** (interview, glossary/ADR upkeep,
  fitness-function pointer), nor the subagent delegation.
