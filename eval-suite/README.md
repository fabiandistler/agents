# R-Code Eval Suite for opencode

Minimal A/B harness to measure what a skill, MCP, or AGENTS.md does to the R
code that opencode generates. Each task is run twice — once with a baseline
config, once with a configured config — and graded with `lintr` + `testthat`.

## Layout

```
tasks/<id>/
  prompt.md     # what opencode is asked to do
  setup.R       # optional, runs in workdir before opencode (creates inputs)
  target.R      # optional, copied into workdir (e.g. function under test)
  tests.R       # testthat file run against the produced solution.R
configs/<name>/
  flags         # optional, extra CLI flags passed to opencode (e.g. --pure)
  model         # optional, model override passed as -m <model> to opencode
  AGENTS.md     # optional, dropped into the workdir as ./AGENTS.md
runs/<ts>/<config>/<task>/
  solution.R    # what opencode produced
  meta.json     # timing, model, environment snapshot, exit code
  test.json     # testthat results
  lint.json     # lintr results
```

## Running

```sh
# run all tasks for both configs (default)
./run.sh

# only one task, only one config
./run.sh --task 03-pkg-state-env --config with-skill

# replay a previous run's scoring without invoking opencode
./run.sh --score-only runs/2026-05-02_19-30-00
```

Then `Rscript score.R runs/<ts>` prints a markdown comparison table and writes
`results.csv`.

## Wiring opencode + your skill

The runner is opencode-agnostic on purpose: it just sets up a workdir, drops
`AGENTS.md` into it, and shells out to `opencode run "<prompt>"`. How skills
get loaded is up to you — typical options:

- Edit `configs/with-skill/AGENTS.md` to inline-reference the skill, e.g.
  `Follow the skill at ~/.agents/r-package-dev/SKILL.md`.
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
| `model` | Model used (`configs/<name>/model` → global opencode config) |
| `opencode_version` | Version of the opencode binary |
| `pure_mode` | `true` when `--pure` is in flags (plugins + MCP disabled) |
| `plugins` | Active plugins (empty when `pure_mode`) |
| `mcp_servers` | Active MCP server names (empty when `pure_mode`) |
| `skills_enabled` | `true` when `AGENTS.md` was injected |
| `context_files` | List of context files copied into the workdir |
| `started_at` / `ended_at` | Unix timestamps |
| `duration_s` | Wall-clock seconds |
| `exit_code` | opencode exit code |
| `mock` | `true` when run via `OPENCODE_MOCK_DIR` |

## Adding a task

1. `mkdir tasks/05-foo && cd tasks/05-foo`
2. Write `prompt.md` (what opencode should produce, in which file)
3. Write `tests.R` — `testthat` expectations against `solution.R`
4. Optional: `setup.R` to create input data, `target.R` to ship a fn-under-test

## Mock mode (for testing the harness itself)

If `OPENCODE_MOCK_DIR` is set, the runner copies fixtures from
`$OPENCODE_MOCK_DIR/<config>/<task>/solution.R` instead of calling opencode.
Useful for verifying `score.R` end-to-end without burning tokens.
