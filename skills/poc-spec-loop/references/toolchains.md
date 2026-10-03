# Toolchains per language

Re-verify the versions below before each real run; `ruff` in particular moves fast.

## Detect

| Language | Marker | Required on PATH | Install line if missing |
|---|---|---|---|
| Python | `pyproject.toml` | `uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| R | `DESCRIPTION` | `R`, `Rscript` | system R ≥ 4.1; packages come via renv in scaffold |
| bash | `*.sh` with `#!/usr/bin/env bash` | `bats`, `shellcheck`, `shfmt` | `apt install bats shellcheck shfmt` (or brew) |

Greenfield: nothing matches → Phase 1 asks once.

## Scaffold (prd item 1)

### Python — uv 0.12 · pytest 9 · ruff 0.16 · ty 0.0.x

```
uv init --package <name> && cd <name>
uv add --dev pytest ruff ty
uv lock && uv sync
```
Pin in `pyproject.toml` — ruff 0.16 expanded the default rule set from 59 to 413. Use `extend-select` (never `select`): `select` replaces the default and silently loses `UP`/`DTZ`/`B`; see `instructions/30-python.md` rationale:
```
[tool.ruff.lint]
extend-select = ["S"]
```
`ty` is the baseline gate (same checker the prek hooks run). `pyright` with `typeCheckingMode = "strict"` or Pyrefly are alternatives — pick exactly one, never two.

Strict opt-in (only if the team asks for it; noisy on throwaway PoC code):
```
[tool.ruff.lint]
extend-select = ["S", "PL", "ANN"]
ignore = ["ANN401"]  # Any in **kwargs allowed

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["ANN", "PLR2004"]
# [tool.ruff]
# line-length = 100        # only if team standard (ruff default is 88)
# target-version = "py312" # only if the repo pins the interpreter
```

Dep/secret hygiene (opt-in, not baseline): `uv add --dev deptry && uv run deptry .` finds unused, missing and transitive imports — run manually or in CI, never as a `local` pre-commit hook (slow, needs a venv). `gitleaks` belongs in the pre-commit hook (last point before a secret lands in history, never CI-only); no pinned fragment exists yet — add it via the prek-hooks skill and set `rev` via `pre-commit autoupdate`, never guessed.

### R — renv 1.2 · testthat 3e · lintr 3.4 · air 0.11 · devtools

```
Rscript -e 'usethis::create_package("."); usethis::use_testthat(3); usethis::use_mit_license()'
Rscript -e 'renv::init()'
Rscript -e 'renv::install(c("testthat","lintr","devtools")); renv::snapshot()'
```
`.lintr` at repo root with defaults; `air` for formatting (`air format .`). No static type checker exists for R — skip.

### bash — bats-core 1.13 · shellcheck 0.11 · shfmt 3.13

```
mkdir -p src test/test_helper
git submodule add https://github.com/bats-core/bats-support test/test_helper/bats-support
git submodule add https://github.com/bats-core/bats-assert  test/test_helper/bats-assert
```

## Commands — the `check` vocabulary for prd items

| Step | Python | R | bash |
|---|---|---|---|
| test | `uv run pytest -q` | `Rscript -e 'testthat::test_local(reporter = "llm")'` | `bats --recursive test/` |
| test one | `uv run pytest tests/test_x.py -q` | `Rscript -e 'testthat::test_file("tests/testthat/test-x.R")'` | `bats test/x.bats` |
| lint | `uv run ruff check . && uv run ruff format --check .` | `Rscript -e 'lintr::lint_package()'` + `air format --check .` | `shellcheck -x src/*.sh && shfmt -d -i 2 -ci .` |
| typecheck | `uv run ty check` | — | — |
| full gate | all of the above | `Rscript -e 'devtools::check(error_on = "warning")'` | all of the above |

`testthat::LlmReporter` (3.3+) emits agent-readable failure output — use it in the loop, not the default reporter. Select it by its short name `"llm"`: testthat appends `Reporter` itself, so `"LlmReporter"` aborts with "Cannot find test reporter".

## CI (prd item 2) — GitHub Actions

One workflow `.github/workflows/ci.yml`, triggered on `pull_request` and `push` to `main`, with `paths-ignore: ["plans/**"]`, running the language's **full gate** row. Python: `astral-sh/setup-uv`; R: `r-lib/actions/setup-r` + `setup-renv`; bash: `apt install` line from Detect.
