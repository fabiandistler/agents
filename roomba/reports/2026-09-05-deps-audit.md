# roomba report — `deps-audit` — 2026-09-05

| Field | Value |
|---|---|
| Job | `deps-audit` (catalogue #1, cooldown 7d) |
| Score | ∞ (never run) |
| Output | report only — this job never bumps versions |
| Baseline before | green, all 10 commands in the ROOMBA.md *Baseline* block |
| Baseline after | unchanged — no code touched |
| Pre-stage | `scripts/roomba-scan.sh deps-audit` → no package inventory (see *Scope*) |

Residual question: **will these updates break me?** Every entry below cites a source that was
read or a command that was run. Nothing is estimated from memory.

## Pre-stage result

`scripts/roomba-scan.sh deps-audit` produced no candidate list. It keys off a repo-root
`DESCRIPTION` / `pyproject.toml` / `requirements.txt`, none of which exist here. Per ROOMBA.md
this counts as **no tooling coverage**, not as "nothing found" — the inventory below was
assembled by hand from the catalogue's repository-specific analogue table.

The scanner did establish one fact on its own: neither Renovate nor Dependabot is configured
(finding 7).

## Findings

### 1 — `actions/checkout@v4`, `actions/setup-python@v5`, `gitleaks/gitleaks-action@v2` declare Node 20, which GitHub removes on 2026-09-23 — **now**

All three actions this repository pins are on the Node 20 runtime. Verified against each tag's
own `action.yml`, not against release prose:

| Action | pinned here | `using:` at that tag | next major | `using:` there |
|---|---|---|---|---|
| `actions/checkout` | `v4` | `node20` | `v7.0.1` | `node24` |
| `actions/setup-python` | `v5` | `node20` | `v7.0.0` | `node24` |
| `gitleaks/gitleaks-action` | `v2` | `node20` | `v3.0.0` | `node24` |

Timeline, from GitHub's own changelog ([Deprecation of Node 20 on GitHub Actions
runners](https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/)):
runners defaulted to Node 24 on **2026-06-16**; Node 20 is removed from runners on
**2026-09-23** — the page carries an editor's note dated 2026-08-25 moving the date there from
the earlier 2026-09-16 that `gitleaks-action@v3`'s release note still quotes. That is **18 days
from today**.

What is *not* documented: the changelog states what the `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION`
opt-out does until removal, but says nothing about how a `using: node20` action behaves after
removal. Mitigating evidence — CI is green today (runs `33961622411`, `33961622392`, 2026-09-05)
and its logs contain no Node 20 deprecation warning, so the runner is already executing these
three actions under Node 24. The break risk is therefore *unknown rather than certain*. It is
still the only finding in this report with a dated deadline.

Breaking changes across the intervening majors, against this repo's actual usage:

- **checkout v4 → v7.** v5: Node 24, requires runner ≥ v2.327.1 (GitHub-hosted: satisfied).
  v6: credentials persisted to a separate file. v7: fork PRs blocked for `pull_request_target`
  and `workflow_run`; ESM migration. This repo uses `checkout` bare in `ci.yml` and with
  `fetch-depth: 0` in `roomba-gate.yml`, and triggers on `push` / `pull_request` only — neither
  the credential change nor the fork-PR block applies. Source: release notes for
  [v5.0.0](https://github.com/actions/checkout/releases/tag/v5.0.0),
  [v6.0.0](https://github.com/actions/checkout/releases/tag/v6.0.0),
  [v7.0.0](https://github.com/actions/checkout/releases/tag/v7.0.0).
- **setup-python v5 → v7.** v6: Node 24; adds `pip-version`, Pipfile parsing; missing cache dir
  downgraded from error to warning. v7: ESM migration; **`pip-install` input removed**. This repo
  passes only `python-version: "3.12"`, so the removed input is not in play. Source: release notes
  for [v6.0.0](https://github.com/actions/setup-python/releases/tag/v6.0.0),
  [v7.0.0](https://github.com/actions/setup-python/releases/tag/v7.0.0).
- **gitleaks-action v2 → v3.** Release note is explicit: "migrates the runtime from Node 20 to
  Node 24. **No changes to inputs, outputs, or behavior.**" This repo passes only
  `GITHUB_TOKEN`. Source:
  [v3.0.0](https://github.com/gitleaks/gitleaks-action/releases/tag/v3.0.0).

Call sites: `.github/workflows/ci.yml:11,13`, `.github/workflows/roomba-gate.yml:22,26`.
Migration effort: four tag edits, no input changes.
**Recommendation: now.** Lowest-cost item in the report against the only hard deadline in it.

### 2 — `mcp[cli]>=1.2` in `mcp-wiki-server/pyproject.toml` already resolves to an incompatible major — **now**

Not a forecast — reproduced. The floor is unpinned, PyPI currently serves `mcp` **2.1.1**, and
`server.py:16` does `from mcp.server.fastmcp import FastMCP`. In a clean venv:

```
$ uv pip install "mcp[cli]"          # → mcp 2.1.1
$ python -c "from mcp.server.fastmcp import FastMCP"
ModuleNotFoundError: No module named 'mcp.server.fastmcp'. This is mcp 2.x, where FastMCP was
renamed to MCPServer (from mcp.server.mcpserver import MCPServer) and other APIs changed; see
the migration guide … or pin 'mcp<2' to keep running v1 code.

$ uv pip install "mcp[cli]<2"        # → mcp 1.29.1
$ python -c "from mcp.server.fastmcp import FastMCP; FastMCP('wiki')"
v1 IMPORT+CONSTRUCT OK; tool= True run= True
```

`mcp-wiki-server/.mcp.json.example` launches the server via `uv run`, which resolves the
declared floor fresh — so anyone following the README today gets 2.1.1 and an import error at
startup. The v2 release note confirms the rename and states v1.x is in maintenance mode
(security fixes only), recommending `<2` for projects not ready to migrate. Source:
[python-sdk v2.0.0](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0),
last v1 release `v1.29.1` (2026-08-24).

Why CI never caught it: nothing in `ci.yml` installs or runs `mcp-wiki-server`; `compileall`
only proves `server.py` parses, not that its import resolves.

Migration effort: **small** if the fix is a `<2` upper bound (one line). **Non-trivial** if the
server is ported to v2 — `FastMCP` → `MCPServer` and the import path change at minimum.
**Recommendation: now**, as the upper bound. Bumping is out of scope for this job (the catalogue
forbids it), so this report only records it; see the tracking issue linked from the PR.

### 3 — `ruff==0.15.8` pin: the deferred cleanup is 12 findings, 9 of them auto-fixable — **with the next feature**

`ci.yml:21` pins ruff with a comment saying 0.16.0 shipped stricter defaults that flag
pre-existing first-party files, and that the bump should ride a deliberate lint-cleanup pass.
The residual question is not *what changed* but *how big the deferred pass is now*. Measured
rather than estimated (current latest is 0.16.6):

```
$ uvx ruff@latest check --statistics .
7  FURB167  [*] regex-flag-alias
2  PLW1510  [ ] subprocess-run-without-check
2  I001     [*] unsorted-imports
1  PLC0206  [ ] dict-index-missing-items
Found 12 errors. [*] 9 fixable with the `--fix` option.
```

Call sites: `scripts/check_plugins.py` (5× FURB167), `scripts/check_docs.py` (2× FURB167),
`mcp-wiki-server/server.py:16` + `scripts/quick_validate.py:12` (I001),
`eval-suite/recall/check_recall.py:104` + `mcp-wiki-server/server.py:38` (PLW1510),
`skills/coupling-cohesion/scripts/coupling_metrics.py:112` (PLC0206).

Note the pin comment is now slightly stale: `EXE001` no longer fires on this repo. The
0.16.0 release note confirms the cause — the default rule set grew from 59 to 413 rules, and
ruff now formats Python blocks inside Markdown by default. Source:
[ruff 0.16.0](https://github.com/astral-sh/ruff/releases/tag/0.16.0).

Migration effort: `--fix` clears 9; three need judgement (two `subprocess.run(check=)` decisions
are behaviour choices, one dict iteration). **Recommendation: with the next feature.** The pin is
working as designed; nothing is degrading while it holds.

### 4 — `shellcheck` is unpinned in CI, but shows no drift across 0.9.0 → 0.11.0 — **leave**

`ci.yml` calls bare `shellcheck`, taking whatever the runner image ships — outside this repo's
control. `ubuntu-latest` currently maps to **ubuntu-24.04**, which ships **shellcheck 0.9.0**;
the ubuntu-26.04 image (public preview, the eventual successor) ships **0.11.0**. Source:
[runner-images README](https://github.com/actions/runner-images) and the two image readmes
(`Ubuntu2404-Readme.md`, `Ubuntu2604-Readme.md`).

Tested both ends of that span against the four scripts CI lints:

```
$ shellcheck 0.9.0  -S warning install.sh scripts/test_install.sh \
      scripts/roomba-scan.sh eval-suite/run.sh   → rc=0
$ shellcheck 0.11.0 -S warning …                 → rc=0
```

So an image bump introduces no new warning-level findings today. (At info level both report
9× SC2086 and 3× SC2016 — already documented as intentional in the `ci.yml` comment, and
below the `-S warning` gate.) **Recommendation: leave.** Pinning would add a maintenance
obligation to buy a risk that measures as zero.

### 5 — `pyyaml>=6` — **leave**

`ci.yml:42`, unpinned floor. Latest is **6.0.3**; no 7.x exists, so the floor cannot pull in a
major bump. Used only by `scripts/quick_validate.py` for frontmatter parsing. Source: PyPI
metadata for `pyyaml`. **Recommendation: leave.**

### 6 — `python-version: "3.12"` — **leave**

`ci.yml:15`. Consistent with `mcp-wiki-server/pyproject.toml`'s `requires-python = ">=3.10"`.
3.12 is in security-fix support well beyond this catalogue's 2026-12-01 review date.
**Recommendation: leave.**

### 7 — Neither Renovate nor Dependabot is configured — **now**, and as its own recommendation

Confirmed by the pre-stage and by inspection: no `.github/dependabot.yml`, no `renovate.json`,
no `.pre-commit-config.yaml`.

Findings 1, 5 and 6 are exactly what a bot answers better than an agent — a version moved, here
is the diff. `jobs.md` is explicit that the pure update mechanism belongs there and not in an
agent run. Recommending `.github/dependabot.yml` with the `github-actions` ecosystem enabled
would have caught finding 1 the day `checkout@v5` shipped, and would let future `deps-audit`
runs spend their whole budget on the residual question instead of on inventory.

Writing that config is deliberately **not** done here: it is the update mechanism, not this
job's output.

## Scope corrections for ROOMBA.md

Two statements in the catalogue did not survive contact with the repository:

1. **"This repository is neither an R package nor a Python package … `pyproject.toml` … This
   repository has none of them."** It has one: `mcp-wiki-server/pyproject.toml`, with a real
   declared dependency — the source of finding 2. The scanner missed it because it looks only at
   the repository root. This sharpens the existing Backlog item with a concrete instruction:
   point the `deps-audit` pre-stage at `mcp-wiki-server/` too, not just `.`.
2. **Scope gap, not audited here.** `eval-suite/*.R` loads `digest`, `jsonlite`, `lintr`,
   `testthat`, `withr` and `yaml` with no `renv.lock` and no version floors anywhere. These are
   absent from ROOMBA.md's "what `deps-audit` means here" table, so they are recorded as a gap
   rather than audited — six unpinned R packages is a report of its own, and the catalogue did
   not ask for it.

## Summary

| # | Item | Recommendation |
|---|---|---|
| 1 | Node 20 removal 2026-09-23 vs. three node20 actions | **now** |
| 2 | `mcp[cli]>=1.2` resolves to incompatible 2.1.1 | **now** |
| 3 | `ruff==0.15.8` pin — 12 findings deferred, 9 auto-fixable | with next feature |
| 4 | `shellcheck` unpinned — no drift 0.9.0 → 0.11.0 | leave |
| 5 | `pyyaml>=6` | leave |
| 6 | `python-version: "3.12"` | leave |
| 7 | No Renovate/Dependabot | **now** (own recommendation) |

7 findings, 0 changes in this PR — `deps-audit` is a report-only job and must not raise versions.

## Note on the baseline count

ROOMBA.md's status line read "all 11 checks"; the *Baseline* block it points at lists **10**
commands. The eleventh was `ci.yml`'s `pip install ruff==0.15.8` step, which is setup, not a
check. The status line is corrected to 10 in this PR.
