# deps-audit — 2026-09-28

Job 1 of the ROOMBA catalogue. Score 3.29 (23 d since 2026-09-05, cooldown 7 d).
Report-only: no version was bumped.

**Headline: nothing is outdated.** All five pinned hook revisions are at the current
latest release. The findings below are therefore not about stale pins but about the two
places where the *next* update will go wrong, and about the catalogue's own map of this
repository having gone stale.

## Baseline

Green, 14/14, captured before the run from the `ci.yml` step sequence
(`uvx ruff@latest` resolved to 0.16.9):

| Check | Status |
|---|---|
| `build_manifest.py --check`, `build_routers.py --check` | pass |
| `check_descriptions.py`, `check_docs.py`, `check_plugins.py` | pass |
| `check_instructions.py`, `check_evals.py` | pass |
| `quick_validate.py` over every `skills/*/SKILL.md` | pass |
| `uvx ruff@latest check .` | pass |
| `python -m compileall -q scripts skills` | pass |
| `pytest skills/release-pr/scripts/test_release_state.py` | pass (16 passed) |
| `shellcheck -S warning` | pass |
| `bash scripts/test_install.sh` | pass |

Two notes on the baseline itself:

- ROOMBA.md's *Baseline* block lists ten commands and is now short of `ci.yml`, which
  also runs `check_instructions.py`, `check_evals.py`, the `release-pr` pytest file and
  `prek run --all-files`. The block was used as a starting point, not as the authority.
- Per the standing WSL caveat this run does **not** claim "ruff is clean": on this host
  ruff reports none of the `flake8-executable` rules (`EXE001`–`EXE003`) whatever the
  file's real mode. CI decides those alone.

## Pre-stage

`scripts/roomba-scan.sh deps-audit` produced no package findings — only its two closing
notes. ROOMBA.md predicted this and attributed it to the scanner's root-only search for
`DESCRIPTION` / `pyproject.toml` / `requirements.txt`. **That attribution no longer
holds** (finding 6): there is no manifest below the root either, so the empty pre-stage
is now a correct answer rather than a blind spot. It still means "no tooling coverage",
so every finding below was established by hand and is cited.

## Findings

### 1 — Every pinned revision is current. Recommendation: leave

Checked against the GitHub release and tag APIs on 2026-09-28.

| Pin | Repo value | Latest | Status |
|---|---|---|---|
| `pre-commit/pre-commit-hooks` | `v6.0.0` | v6.0.0 (2025-08-09) | current |
| `astral-sh/ruff-pre-commit` | `v0.16.9` | v0.16.9 (2026-09-24) | current |
| `astral-sh/ty-pre-commit` | `v0.0.84` | v0.0.84 (2026-09-24) | current |
| `posit-dev/air-pre-commit` | `0.11.0` | 0.11.0 (2026-07-21) | current |
| `lorenzwalthert/precommit` | `v0.4.3.9032` | v0.4.3.9032 | current |

Consistent with `.pre-commit-config.yaml:1`, whose header records a regeneration on
2026-09-28 — `prek update --cooldown-days 7` ran today. Nothing to migrate, no call
sites to change, no effort to estimate.

### 2 — The current `ty` pin is a security fix. Recommendation: leave, and see finding 3

`ty` 0.0.84 exists to close
[GHSA-vxvm-j4xq-q7m4](https://github.com/astral-sh/ty/security/advisories/GHSA-vxvm-j4xq-q7m4):
a use-after-free during incremental type checking that can reach arbitrary code
execution when ty analyses a specially crafted Python project
([release notes, 0.0.84](https://github.com/astral-sh/ty/releases/tag/0.0.84), read).

Both copies of the pin are on the patched revision —
`.pre-commit-config.yaml:37` and `skills/prek-hooks/references/fragments/python.yaml:20`
— so there is no exposure today. It is recorded because it sets the stakes for
finding 3: the fragment copy is what other repositories bootstrap from, and it is the
copy that no tool keeps current.

On breaking-change risk for the *next* `ty` bump: six releases shipped between
2026-09-07 and 2026-09-24 (roughly one every three days) and none carries a "breaking
changes" section. The risk in a `ty` bump is not an API break but a shifting diagnostic
set inside a blocking gate — 0.0.84 alone changes core inference in eight places and
flips `invalid-legacy-positional-parameter` off by default. At 0.0.x that arrives in
patch-level bumps, which is the argument for keeping the rev pinned rather than floating.

### 3 — Three revisions live in two files, and the documented update path only rewrites one. Recommendation: now

`.pre-commit-config.yaml` is generated: its header names `setup-hooks.sh`, and the file
is the concatenation of `references/fragments/base-compat.yaml` and
`references/fragments/python.yaml` plus exactly two local additions — the
`exclude: '(^|/)(fixtures|bad_examples)/'` line and
`additional_dependencies: ["pyyaml>=6"]`. Verified by diffing the concatenation against
the live file with comments and blank lines stripped.

So `pre-commit-hooks`, `ruff-pre-commit` and `ty-pre-commit` are each pinned twice:

| Rev | Live config | Shipped fragment |
|---|---|---|
| `pre-commit-hooks` | `.pre-commit-config.yaml:10` | `fragments/base-compat.yaml:7` |
| `ruff-pre-commit` | `.pre-commit-config.yaml:24` | `fragments/python.yaml:7` |
| `ty-pre-commit` | `.pre-commit-config.yaml:37` | `fragments/python.yaml:20` |

They agree today. The problem is the update path: the header of
`.pre-commit-config.yaml` and `setup-hooks.sh:107` both prescribe
`prek update --cooldown-days 7`, and that rewrites the generated config only. The
fragments — the artefact the `prek-hooks` skill hands to other repositories — stay at
whatever they were. Nothing in `ci.yml` compares them.

This repository gates exactly this class of invariant everywhere else: `skills.json` via
`build_manifest.py --check`, router bodies via `build_routers.py --check`, catalogue
tables via `check_docs.py`, the marketplace via `check_plugins.py`, `instructions/` via
`check_instructions.py`. The prek fragments are the one generated-pin surface with no
`--check` behind them.

Taken with finding 2, the concrete failure is: the next `ty` advisory lands, this repo's
own pin moves because `prek update` runs here, and the shipped fragment keeps handing new
repositories the unpatched revision.

The fix is a new check script plus a CI step. That is a behaviour change and out of scope
for a report-only job, so it goes to *Backlog* rather than into this PR.

### 4 — CI installs `prek` unpinned, and `prek` shipped a breaking release five weeks ago. Recommendation: with next feature

`ci.yml:66` is a bare `pip install prek`, feeding the blocking *Hooks in sync (prek)*
step. prek
[v0.5.0](https://github.com/j178/prek/releases/tag/v0.5.0) (2026-08-27, release notes
read) removed `prek auto-update`, removed `prek init-template-dir`, removed
`PREK_MAX_CONCURRENCY`, and reserved a leading `@` in group names. CI currently resolves
to v0.5.4, released 2026-09-28.

Checked before reporting: no tracked file uses any removed name —
`setup-hooks.sh:107` already calls `prek update`, and there is no reference to
`auto-update`, `init-template-dir` or `PREK_MAX_CONCURRENCY` anywhere in the repository.
The boundary was crossed without damage.

Worth separating from ruff: ruff's unpinning is a recorded decision (`ee36b79`, "Unpin
ruff and clear the findings the pin was deferring") and is not re-litigated here. No
comparable decision exists for `prek`, which looks incidental — it entered with the
original hook-gate commit `3c20aa7`. The recommendation is deliberately soft: a floating
0.x dependency in a blocking gate is worth *knowing about*, and worth pinning the first
time the gate breaks for no reason anyone can reproduce.

`pytest` (`ci.yml:61`) is likewise unpinned; it is 1.x-stable and drives one fixture
file, so: leave. The `pyyaml>=6` floor (`ci.yml:42`, `python.yaml`'s
`additional_dependencies`) is a floor rather than a pin and needs nothing.

### 5 — Dependabot's scope still covers every action tag. Recommendation: leave

ROOMBA.md asks a run to confirm the config still covers the action tags rather than
re-checking each by hand. It does. Three distinct tags exist across both workflows:

- `actions/checkout@v7`, `actions/setup-python@v7` — `ci.yml`
- `anthropics/claude-code-action@v1` — `claude.yml` (plus `actions/checkout@v7`)

`.github/dependabot.yml` declares `package-ecosystem: github-actions` with
`directory: /`, which covers `.github/workflows/**`; both workflows live there and
`git ls-files .github/workflows/` lists no others. The grouped weekly PR therefore still
sees all three.

### 6 — The catalogue's own dependency map points at code that no longer exists. Recommendation: now

ROOMBA.md's *"what `deps-audit` means here"* table and several Backlog entries are built
on `mcp-wiki-server/pyproject.toml` and `eval-suite/`. Both were extracted into their own
repositories (merge commits `3fb52f0` → PR #148, `80abc3c` → PR #147).

Evidence: `git ls-files | grep -E 'eval-suite|mcp-wiki|pyproject\.toml'` returns nothing.
**No `pyproject.toml` is tracked anywhere in this repository**, at the root or below it.
`check_live.py`, `check_recall.py` and `import_vitals.R` are likewise untracked.

What that invalidates:

- The `mcp[cli]>=1.2,<2` finding from the 2026-09-05 run is moot; the row naming it as
  what `deps-audit` covers here is wrong.
- The Backlog item *"`eval-suite/*.R` dependencies … decide whether they belong in
  `deps-audit` before the next run of that job"* addressed this run. It resolves by
  obsolescence: those files are not in this repository.
- The Backlog item on adapting `roomba-scan.sh` keeps its root-only critique as a general
  scanner limitation, but loses its cited motivation — there is no manifest below the root
  to find.
- The Backlog items on `check_live.py` and `recall/check_recall.py` (both tied to issue
  #95) and on `import_vitals.R` describe code that now belongs to the extracted
  repositories.

This is the one finding this run acts on, in ROOMBA.md itself. The catalogue is
documentation, and a stale map of the repository is what makes the next run waste its
slot — this run's own pre-stage is the demonstration.

## Recorded, not investigated

Surfaced while establishing the findings above; each is outside `deps-audit` and is filed
as a single Backlog line without further work.

- `roomba-gate.yml` was deliberately deleted (`58fc561`). ROOMBA.md still claims
  `security-footguns` runs in CI as `roomba-gate → gitleaks`, so that row is now false and
  the repository has no secret scanning on `main`. Not re-added here: restoring a
  deliberately removed gate is a decision, not maintenance.
- The `.serena/` Backlog item is resolved — the directory is gone and the tree is clean.
- `.pre-commit-config.yaml`'s comment advises pinning the rule set with `select`, where
  `ruff.toml` correctly uses `extend-select`. Documentation drift, so `doc-drift`'s to take.

## Automation

Dependabot is configured and its scope is correct (finding 5). The mechanical half of this
job is already delegated; what stays manual is the two-copy pin surface in finding 3,
which no bot can see because the fragments are not a manifest.

## Next job

`doc-drift` (job 2), score 1.64, overdue since 2026-09-19. Findings 6 and the third
*Recorded* item above are already routed to it.
