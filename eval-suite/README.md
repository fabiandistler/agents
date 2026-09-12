# R-Code Eval Suite for opencode

A/B harness that measures what a skill, MCP server, or `AGENTS.md` changes in
the R code opencode generates. Every task in `tasks/` runs under every config
in `configs/`; each `solution.R` is graded with `lintr` + `testthat` plus an
LLM judge.

The suite ships 33 tasks: 4 custom tasks with `testthat` test suites, and 29
tasks imported from the [tidyverse/vitals ARE benchmark](https://github.com/tidyverse/vitals/tree/main/data-raw)
covering tidyverse, ggplot2, and r-lib R coding challenges.

Scope: this measures output quality once a skill is *already* loaded (via
`AGENTS.md`). Whether a collapsed router category still triggers the right
skill is a separate check — see `recall/README.md`.

## Quick start

Assumptions: Debian/Ubuntu, R available, `opencode` on `PATH`. This first run
uses mock solutions, so it needs no tokens and skips the judge:

```sh
apt-get install r-base-core r-cran-{testthat,lintr,yaml,jsonlite,withr,digest,data.table,dbi,rsqlite}
OPENCODE_MOCK_DIR=fixtures ./run.sh --task 01-dt-aggregate
xdg-open runs/*/viewer.html        # Linux; `open` on macOS
```

A real two-config comparison of one task:

```sh
./run.sh --task 01-dt-aggregate
```

## Layout

```
tasks/<id>/
  task.yaml     # id, title, prompt, expectations OR target (for the LLM judge)
  setup.R       # optional, creates input files (re-run at scoring time)
  target.R      # optional, copied into workdir (e.g. function under test)
  tests.R       # optional, testthat file run against the produced solution.R
configs/<name>/
  flags         # optional, extra CLI flags passed to opencode (e.g. --pure)
  model         # optional, model override passed as -m <model> to opencode
  AGENTS.md     # optional, dropped into the workdir as ./AGENTS.md
runs/<ts>/
  score.csv         # raw lintr+testthat counts per (config, task)
  results.csv       # score.csv + judge counts merged
  results.md        # markdown summary (per-task, overall, delta)
  viewer.html       # self-contained HTML viewer (open in browser)
  <config>/<task>/
    solution.R      # what opencode produced
    meta.json       # timing, model, environment snapshot, exit code
    judge.json      # LLM-judge expectations + evidence
    opencode.stdout # captured stdout from opencode run
    opencode.stderr # captured stderr from opencode run
```

`runs/` is gitignored. `viewer.html` is rendered from `viewer.html.template`
with the run data embedded, so it works with no server and no CDN.

## Configuration

Environment variables (`run.sh --help` lists the same):

| Name | Default | Effect |
|---|---|---|
| `OPENCODE_BIN` | `opencode` | CLI under test. The runner relies on `opencode run` (plus `--pure` for the baseline), so other coder CLIs are not drop-in replacements. |
| `JUDGE_CLI` | `claude` | CLI used for LLM-as-judge scoring. Supported: `claude`, `codex`, `opencode`. Independent of `OPENCODE_BIN`. |
| `JUDGE_MODEL` | `claude-sonnet-5` | Model passed to the judge CLI. Must name a model that is still served — a retired id makes every call fail and the judge column silently collapses to `judge: —`. |
| `NO_JUDGE` | unset | Set to `1` (or pass `--no-judge`) to skip the judge step. |
| `OPENCODE_MOCK_DIR` | unset | Set to `fixtures` to copy mock solutions instead of calling opencode. Judge is skipped automatically. |

Per-config files under `configs/<name>/`:

| File | Effect |
|---|---|
| `flags` | Extra flags for the `opencode run` call. `--pure` additionally clears the recorded plugins/MCP servers and sets `pure_mode: true` in `meta.json`. |
| `model` | Overrides the model recorded in `meta.json` and passed as `-m <model>`; otherwise the model is read from the global opencode config. |
| `AGENTS.md` | Copied to the workdir as `./AGENTS.md`; its presence sets `skills_enabled: true` in `meta.json`. |

## Usage

```sh
# all tasks, all configs
./run.sh

# one task, all configs / all tasks, one config / one of each
./run.sh --task 03-pkg-state-env
./run.sh --config with-skill
./run.sh --task 01-dt-aggregate --config baseline

# skip the LLM judge step
./run.sh --no-judge

# replay scoring + judge + aggregation + viewer over an existing run
./run.sh --score-only runs/2026-05-02_19-30-00
```

`run.sh` executes all `(config, task)` pairs first, then finalizes the whole
run directory: `score.R` (lintr + testthat → `score.csv`) →
`judge.R` (LLM judge → `<config>/<task>/judge.json`) →
`aggregate.R` (merge → `results.{csv,md}`) →
`generate_viewer.R` (`viewer.html`).

## Wiring opencode + your skill

The runner sets up a workdir, drops `AGENTS.md` into it, and shells out to
`opencode run "<prompt>"`. How skills get loaded is up to you — typical
options:

- Edit `configs/with-skill/AGENTS.md` to inline-reference the skill, e.g.
  `Follow the skill at ~/.agents/<skill-name>/SKILL.md`.
- Or load the skill via your global opencode config and leave `AGENTS.md` as
  a bare opt-in marker.

The `baseline` config uses `--pure` (via `configs/baseline/flags`) to disable
all plugins and MCP servers, giving a clean control without any skill influence.

## meta.json fields

Each run writes a `meta.json` with the full environment snapshot:

| Field | Description |
|---|---|
| `config` | Config name |
| `task` | Task ID |
| `opencode_flags` | Flags from the config's `flags` file |
| `model` | `configs/<name>/model` if present, else the model from the global opencode config |
| `opencode_version` | Version of the opencode binary |
| `pure_mode` | `true` when `--pure` is in flags (plugins + MCP disabled) |
| `plugins` | Active plugins from the global opencode config (empty when `pure_mode`) |
| `mcp_servers` | Active MCP server names from the global opencode config (empty when `pure_mode`) |
| `skills_enabled` | `true` when `AGENTS.md` was injected |
| `context_files` | List of context files copied into the workdir |
| `started_at` / `ended_at` | Unix timestamps |
| `duration_s` | Wall-clock seconds |
| `exit_code` | opencode exit code |
| `mock` | `true` when run via `OPENCODE_MOCK_DIR` |

## LLM judge

After `lintr` + `testthat`, `judge.R` feeds each `solution.R` plus its
objective score (tests passed, lint warnings, parses) to the judge CLI and
expects strict JSON back. Two grading modes are supported:

- **Expectations mode** — task.yaml has an `expectations` list; each item is
  graded pass/fail with a short evidence quote.
- **Target mode** — task.yaml has a `target` (reference solution + grading
  notes) instead of `expectations`; the judge derives 3–5 concrete criteria
  from the target and evaluates the solution against them.

Result lands in `runs/<ts>/<config>/<task>/judge.json`, which records
`judge_model` and `judge_prompt_sha256` so reruns can detect drift.

The judge is skipped entirely when `--no-judge` is passed (or `NO_JUDGE=1`),
when `OPENCODE_MOCK_DIR` is set, or when the `JUDGE_CLI` binary is not on
`PATH`. Additionally, a single `(config, task)` gets a stub `judge.json` with
`skipped: true` and a `reason` when no `solution.R` was produced or when that
judge call itself failed — `judge.R` logs a `[judge] FAILED …` line per failed
call but still writes the report. `results.md` prints a **Judge broken**
banner when failures (e.g. a retired `JUDGE_MODEL` id) are the cause.

Caveat for **target mode**: the judge derives its own criteria per call, so
the criteria count can differ between the two configs for the same task. The
`Δ judge passed` column is therefore only comparable for expectations-mode
tasks, where both configs are graded against the same fixed list.

Cost: ~1 API call per (config, task), so the default 2 × 33 = 66 calls per run.
Use `--task <id>` to run a subset.

## Reading the results

`score.csv` holds one row per `(config, task)`: solution present, parses,
lint count, line count, testthat totals, plus `pass_rate` and `test_run_error`
when the test file itself crashes. `results.csv` adds the judge columns
(`judge_pass`, `judge_total`, `judge_pass_rate`, `judge_skipped`,
`judge_model`, `judge_reason`).

`results.md` renders three tables:

- **Per-task** — per config: `N/M tests · K lint · judge: P/Q`. Special cells:
  `**no file**` (no `solution.R`), `**test crash**` (the test run errored),
  `judge-only` (task has no `tests.R`), `judge: —` (judge skipped).
- **Overall** — summed tests, lint, and judge counts per config.
- **Delta** — only when exactly two configs are present: `b − a` differences
  for passed tests, lint warnings, and judge passes, with `a` the
  alphabetically first config.

## HTML viewer

`generate_viewer.R` writes `runs/<ts>/viewer.html` — a self-contained file
(no CDN, no server) showing per-task side-by-side: solution code, test/lint
badges, expandable judge expectations with evidence. Open it directly:

```sh
xdg-open runs/<ts>/viewer.html        # Linux
open runs/<ts>/viewer.html            # macOS
```

## Adding a task

1. `mkdir tasks/05-foo && cd tasks/05-foo`
2. Write `task.yaml` with `id`, `title`, `prompt`, and either:
   - `expectations` — explicit list of pass/fail criteria the LLM judge evaluates, or
   - `target` — a reference solution / grading rubric; the judge derives criteria from it
3. Optional: `tests.R` — `testthat` expectations against `solution.R` (objective score; tasks without it are judge-only and show up as `judge-only` in the test column)
4. Optional: `setup.R` to create input data, `target.R` to ship a fn-under-test

`setup.R` runs twice: once in the workdir before opencode is called (so the
model can sanity-check against the inputs), and again in an isolated tempdir
at scoring time (so `tests.R` sees the same inputs). `target.R` is copied to
both places as well. Imported vitals tasks may also carry `domain`,
`task_type`, `source`, and `knowledge` metadata in `task.yaml`; these are
informational only.

### Importing tasks from vitals

`import_vitals.R` is a one-shot script that downloads the ARE tasks from
`tidyverse/vitals` (29 task directories in the current tree) and creates a
`tasks/<slug>/` directory for each. Re-running is safe (idempotent, skips
existing dirs):

```sh
Rscript import_vitals.R
```

Imported tasks use the `target` grading mode and have no `tests.R`.

## Mock mode (for testing the harness itself)

If `OPENCODE_MOCK_DIR` is set, the runner copies fixtures from
`$OPENCODE_MOCK_DIR/<config>/<task>/solution.R` instead of calling opencode.
The judge is skipped automatically. Useful for verifying `score.R`,
`aggregate.R`, and `generate_viewer.R` end-to-end without burning tokens.

`fixtures/` only covers the four custom tasks; the 29 vitals tasks have no
fixture. A mock run records `exit_code: 127` for those and they show up as
**no file** — that is expected, mock mode exercises the harness, not the task
bank.
