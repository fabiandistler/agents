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
uv add --dev ruff ty pytest pytest-cov pip-audit
uv lock && uv sync
```
Pin in `pyproject.toml`. Use `extend-select`, never `select`: since ruff 0.16 the default set (413 rules, up from 59) covers `UP`/`DTZ`/`B`, and `select` would replace it. A fresh `uv init --package` passes this set; keep it passing rather than narrowing the rules. `exclude-newer` needs uv ≥ 0.9.17 — on an older uv leave the line out:
```
[tool.ruff.lint]
extend-select = ["S"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]  # pytest asserts

[tool.coverage.run]
branch = true

[tool.uv]
exclude-newer = "7 days"
```
`ty` is the single type-check gate (same checker the prek hooks run). It is still beta; if it breaks on a library, swap it for `mypy` with `[tool.mypy] strict = true` — one checker, never two.

Strict opt-in (only if the team asks for it; noisy on throwaway PoC code):
```
[tool.ruff.lint]
extend-select = ["S", "PL", "ANN"]

[tool.ruff.lint.flake8-annotations]
allow-star-arg-any = true  # Any on *args/**kwargs only; ANN401 still flags it elsewhere

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "ANN", "PLR2004"]
```

Dependency hygiene (opt-in, not baseline): `uv add --dev deptry && uv run deptry .` finds unused, missing and transitive imports. Run it in the full gate or CI rather than on every commit: it needs the project environment installed. Secret scanning belongs in the commit hook, not this loop; see the prek-hooks skill.

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
