# R-Code Eval Suite for opencode

Minimal harness to measure what a skill, MCP, plugin, or AGENTS.md does to
the R code that opencode generates. Each task is run once per config (one is
expected to be `baseline`, the rest are whatever you want to compare against)
and graded with `lintr` + `testthat`. With `baseline` present, the aggregator
emits a per-config delta table against it.

The suite ships 33 tasks: 4 custom tasks with `testthat` test suites, and 29
tasks imported from the [tidyverse/vitals ARE benchmark](https://github.com/tidyverse/vitals/tree/main/data-raw)
covering tidyverse, ggplot2, and r-lib R coding challenges.

## Layout

```
tasks/<id>/
  task.yaml     # id, title, prompt, expectations OR target (for the LLM judge)
  setup.R       # optional, runs in workdir before opencode (creates inputs)
  target.R      # optional, copied into workdir (e.g. function under test)
  tests.R       # optional, testthat file run against the produced solution.R
configs/<name>/
  flags         # optional, extra CLI flags passed to opencode (e.g. --pure)
  model         # optional, model override passed as -m <model> to opencode
  AGENTS.md     # optional, dropped into the workdir as ./AGENTS.md
  opencode.json # optional, per-config opencode config (mcp/plugin/provider/...)
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

## Running

```sh
# run all tasks for both configs (default)
./run.sh

# only one task, only one config
./run.sh --task 03-pkg-state-env --config with-skill

# skip the LLM judge step
./run.sh --no-judge

# replay scoring + judge + aggregation + viewer over an existing run
./run.sh --score-only runs/2026-05-02_19-30-00
```

`run.sh` orchestrates four phases after each opencode call:
`score.R` (lintr + testthat → `score.csv`) →
`judge.R` (LLM judge → `<config>/<task>/judge.json`) →
`aggregate.R` (merge → `results.{csv,md}`) →
`generate_viewer.R` (`viewer.html`).

## Configuring what each arm tests

The runner is opencode-agnostic: for each config it sets up a sandboxed
workdir, drops the configured artifacts into it, and shells out to
`opencode run "<prompt>"`. Each `configs/<name>/` directory can contain any
combination of:

| File | Effect |
|---|---|
| `flags` | Extra CLI flags appended to `opencode run` (e.g. `--pure`) |
| `model` | Model name; passed as `-m <model>` (overrides anything in `opencode.json`) |
| `AGENTS.md` | Dropped into the workdir as `./AGENTS.md` so opencode loads it |
| `opencode.json` | Per-config opencode config; copied into the run's sandboxed `XDG_CONFIG_HOME/opencode/opencode.json`. Lets you declare `mcp`, `plugin`, `provider`, `instructions`, `mode`, etc. per config |

The `baseline` config carries only `flags` with `--pure` and nothing else, so
the sandboxed opencode sees no AGENTS.md, no MCP, no plugins, and no provider
overrides — a clean control.

Examples of what you can A/B-test by adding a new `configs/<name>/`:

- **Skill via AGENTS.md** — `configs/with-skill/AGENTS.md` (current example).
- **MCP server** — `configs/with-mcp-fetch/opencode.json` containing
  ```json
  { "$schema": "https://opencode.ai/config.json",
    "mcp": { "fetch": { "type": "local", "command": ["uvx", "mcp-server-fetch"] } } }
  ```
- **Plugin** — `configs/with-plugin-x/opencode.json` with a `plugin` array.
- **Alternate provider/model** — `configs/with-haiku/opencode.json` setting
  `provider`/`model`.

You can mix artifacts (e.g. an `AGENTS.md` plus an `opencode.json` with an
MCP) to test combined effects.

## Isolation guarantees

For each `(config, task)` pair the runner builds a sandbox before invoking
opencode, so the user's host environment cannot taint the run:

- **Workdir**: `runs/<ts>/.work/<config>-<task>/` (controlled, not `/tmp`).
- **`env -i` allowlist**: only `PATH`, `USER`, `LANG`, `LC_ALL`, `TERM` and the
  API-key vars (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`,
  `GOOGLE_API_KEY`, `GEMINI_API_KEY`) are forwarded. Everything else —
  including all `OPENCODE_*` and `CLAUDE_*` host vars — is dropped.
- **`HOME` and `XDG_CONFIG_HOME`** are pinned to a per-run sandbox dir, so
  opencode never reads `~/.config/opencode/opencode.json` from the host.
- **AGENTS.md walk-up check**: before the run, the parent chain of the workdir
  is scanned for stray `AGENTS.md` files. If any exists, the run aborts with
  a clear error rather than silently picking it up.
- **`--pure`** in the baseline `flags` is kept as belt-and-suspenders even
  though the XDG sandbox already prevents user-config loading.

If you need additional env vars to reach opencode (e.g. an API base URL),
extend `ENV_ALLOWLIST_BASE` / `ENV_ALLOWLIST_KEYS` at the top of `run.sh`.

## meta.json fields

Each run writes a `meta.json` with the full environment snapshot:

| Field | Description |
|---|---|
| `config` | Config name |
| `task` | Task ID |
| `opencode_flags` | Flags from the config's `flags` file |
| `model` | Model used (`configs/<name>/model` → global opencode config) |
| `opencode_version` | Version of the opencode binary |
| `pure_mode` | `true` when `--pure` is in flags |
| `plugins` | Plugins declared in the config's `opencode.json` (empty when none) |
| `mcp_servers` | MCP server names declared in the config's `opencode.json` (empty when none) |
| `skills_enabled` | `true` when `AGENTS.md` was injected |
| `opencode_config_used` | `true` when the config supplied an `opencode.json` |
| `context_files` | List of context files copied into the workdir |
| `started_at` / `ended_at` | Unix timestamps |
| `duration_s` | Wall-clock seconds |
| `exit_code` | opencode exit code |
| `mock` | `true` when run via `OPENCODE_MOCK_DIR` |

## LLM judge

After `lintr` + `testthat`, `judge.R` asks `claude` (via the local CLI) to
evaluate each `solution.R`. Two grading modes are supported:

- **Expectations mode** — task.yaml has an `expectations` list; each item is
  graded pass/fail with a short evidence quote.
- **Target mode** — task.yaml has a `target` (reference solution + grading
  notes) instead of `expectations`; the judge derives 3–5 concrete criteria
  from the target and evaluates the solution against them.

Result lands in `runs/<ts>/<config>/<task>/judge.json`.

The judge is automatically skipped when:

- `--no-judge` is passed (or `NO_JUDGE=1`)
- `OPENCODE_MOCK_DIR` is set (mock mode)
- the `claude` binary is not on `PATH`

In skip cases, `judge.R` still writes a stub `judge.json` with `skipped: true`
so downstream aggregation and the viewer handle it uniformly.

Override the judge model with `JUDGE_MODEL=claude-...` (default
`claude-sonnet-4-5`). Each `judge.json` records `judge_model` and
`judge_prompt_sha256` so reruns can detect drift.

Cost: ~1 API call per (config, task). With the shipped 2 configs and 33 tasks
that's 66 calls per run; adding a third config (e.g. `with-mcp`) makes it 99.
Use `--task <id>` or `--config <name>` to run a subset.

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
3. Optional: `tests.R` — `testthat` expectations against `solution.R` (objective score; tasks without it are judge-only)
4. Optional: `setup.R` to create input data, `target.R` to ship a fn-under-test

### Importing tasks from vitals

`import_vitals.R` is a one-shot script that downloads the 29 ARE tasks from
`tidyverse/vitals` and creates a `tasks/<slug>/` directory for each. Re-running
is safe (idempotent, skips existing dirs):

```sh
Rscript import_vitals.R
```

Imported tasks use the `target` grading mode and have no `tests.R`.

## Mock mode (for testing the harness itself)

If `OPENCODE_MOCK_DIR` is set, the runner copies fixtures from
`$OPENCODE_MOCK_DIR/<config>/<task>/solution.R` instead of calling opencode.
The judge is skipped automatically. Useful for verifying `score.R`,
`aggregate.R`, and `generate_viewer.R` end-to-end without burning tokens.
