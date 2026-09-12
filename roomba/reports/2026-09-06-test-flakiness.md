# roomba — `test-flakiness`, 2026-09-06

Baseline before the run: **green**, all 10 commands from *Baseline* in `ROOMBA.md`.
Output: 4 findings, 1 fixed, 3 report-only.

## Pre-stage: no tooling coverage

```console
$ scripts/roomba-scan.sh test-flakiness
kein tests/ oder test/ Verzeichnis gefunden
exit=0
```

The scanner searches only root-level `tests/` and `test/`. This repository's tests live in
`eval-suite/` and `scripts/test_install.sh`, so the pre-stage saw nothing. Per
*Repository-specific notes on the pre-stages* this is recorded as **no tooling coverage**,
not as "no flaky tests".

Compensated by running the scanner's **own grep patterns** — time, random, network, sleep,
plus its two counter-probes — against the locations the catalogue's analogue table names.
The patterns are the scanner's, not hand-invented; only the search root differs.

## Finding 1 — the test corpus is deterministic — **negative result, no change**

| Probe | Result |
|---|---|
| time (`Sys.time`, `Sys.Date`, `datetime.now`, `time.time`, `date.today`) | none |
| sleep (`Sys.sleep`, `time.sleep`) | none |
| random | 1 real hit, seeded — see below |
| network in test code | none |

The single unseeded-random candidate is answered by the scanner's own counter-probe:

```
eval-suite/tasks/01-dt-aggregate/setup.R:2  withr::local_seed(1)
eval-suite/tasks/01-dt-aggregate/setup.R:4-7  sample(...), sample(...), sample(...), runif(...)
```

The seed precedes every draw, and uses `withr::local_seed()` rather than `set.seed()` —
already the convention this repository follows. Nothing to fix.

The four graded task suites (`eval-suite/tasks/0[1-4]/tests.R`) build their fixtures from
hard-coded literals (`make_dt()`), not from `setup.R`'s random data, so the assertions do
not depend on the seeded values at all. `scripts/test_install.sh` runs each case under an
isolated `HOME` from `mktemp -d`. `eval-suite/run.sh` orders directories with
`find … | sort`, runs no jobs in parallel, and uses `date` only for the run ID and for
duration output — never in an assertion.

**Not flagged, deliberately:** `eval-suite/tasks/nested-servers/task.yaml:41-42` contains
`sample(1:25, 25)` without a seed. It is inside the Shiny snippet that forms the *task
prompt* — imported benchmark content the model is asked to reason about, not test code.
Path and purpose were checked before deciding.

## Finding 2 — `import_vitals.R` fetched a moving ref — **fixed**

`eval-suite/import_vitals.R:13` pointed at the upstream default branch:

```r
ARE_URL <- ".../tidyverse/vitals/main/data-raw/are.json"
```

Re-running the importer at any later date could therefore produce a different task corpus
from the same commit of this repository, with nothing in the repo recording which upstream
state the committed tasks came from. The script skips directories that already exist, so
drift would appear only in newly added tasks — silently, and mixed in with the old ones.

This is the one place in the eval suite where the job's rule applies literally: replace the
source of nondeterminism, change no assertion. Pinned to the commit that last touched the
file, `58609f04a3c36f336c552f8cc578ac38b1e88592` (2025-06-18, "regenerate `are`").

**Proof the pin changes nothing today:**

```console
$ curl -sS .../vitals/58609f0.../data-raw/are.json -o are_pin.json   # 29 tasks
$ curl -sS .../vitals/main/data-raw/are.json      -o are_main.json   # 29 tasks
$ cmp are_pin.json are_main.json && echo byte-identical
byte-identical
```

The two fetches are byte-identical, so the importer's behaviour is unchanged for any run
made today; only future reproducibility improves. No test asserts on this script, and it is
called by neither `run.sh` nor CI — it is a one-shot corpus generator (`README.md:144`).

## Finding 3 — recall is scored from a single sample of a nondeterministic oracle — **report-only**

`eval-suite/recall/check_recall.py` asks a live model one question per prompt
(`for item in prompts:` → one `ask_model` call each, `:126`) and reports the hit count as a
bare score. No repetition, no spread, and `eval-suite/recall/README.md` documents no
variance at all — a grep for *variance*, *repeat*, *nondeterministic*, *temperature* and
*seed* returns nothing.

The residual question this job asks is whether the nondeterminism is intentional. Here it
is **inherent and unavoidable**: the oracle is an LLM behind `claude -p`, which exposes no
seed or temperature control, so it cannot be replaced the way a clock or an RNG can. What
is *not* intentional is presenting one draw as a measurement. Two runs of an unchanged
description can differ, and nothing in the output says so.

**No change.** Repeating each prompt N times and reporting the spread changes what the
harness computes — a behaviour change, outside this job. Recorded for whoever fixes #95.

## Finding 4 — `import_vitals.R:8` says 31 tasks; there are 29 — **report-only, routed**

The header comment claims "31 ARE tasks"; `README.md:144` says 29. Counted from the source
of truth, twice: `len(json.load(are.json))` is **29** at both the pinned SHA and `main`.
The 33 directories under `eval-suite/tasks/` are those 29 plus the four hand-written
suites `01-dt-aggregate` … `04-testthat-suite`, which reconciles exactly.

Left unfixed on purpose: a wrong number in a comment is documentation drift, not a source
of nondeterminism, so it belongs to `doc-drift` (job 2, due 2026-09-19) rather than here.
Recorded so that run does not have to rediscover the count.
