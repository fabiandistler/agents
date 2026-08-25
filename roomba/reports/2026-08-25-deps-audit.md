# deps-audit — 2026-08-25

Job 1 of the [ROOMBA catalogue](../../ROOMBA.md). Report only; no code was
changed in this run.

## Scope

Everything this repository declares, pins, or shells out to:

| Surface | Declared where | Constraint today |
|---|---|---|
| `mcp[cli]` | `mcp-wiki-server/pyproject.toml` | `>=1.2` |
| `hatchling` | `mcp-wiki-server/pyproject.toml` (build) | unbounded |
| `pyyaml` | `skills/skill-creator/pyproject.toml`, `.github/workflows/ci.yml` | `>=6` |
| `ruff` | `.github/workflows/ci.yml` | `==0.15.8` |
| `actions/checkout` | `.github/workflows/ci.yml` | `@v4` |
| `actions/setup-python` | `.github/workflows/ci.yml` | `@v5` |
| R packages (eval-suite) | nowhere | undeclared |
| `Rscript`, `opencode`, `jq`, `shellcheck` | nowhere | undeclared |

Vulnerability data came from the GitHub Advisory Database (osv.dev is
unreachable from this environment). Version data came from the PyPI JSON API
and the upstream release pages, all read on 2026-08-25.

## Findings

Ordered by severity.

---

### F1 — `mcp[cli]>=1.2` is unbounded and a fresh install is broken today

**Severity: high — already broken, not a future risk.**

`mcp-wiki-server/pyproject.toml:6` declares `dependencies = ["mcp[cli]>=1.2"]`
with no upper bound. `mcp-wiki-server/server.py:16` imports:

```python
from mcp.server.fastmcp import FastMCP
```

mcp 2.0.0 (released 2026-07-28) renamed `FastMCP` to `MCPServer` and removed
the `mcp.server.fastmcp` module. The current release is 2.1.0 (2026-08-24), so
that unbounded floor resolves to 2.1.0 and the server no longer imports.

Reproduced both directions in a clean venv:

```
$ pip install "mcp[cli]"        # resolves 2.1.0
$ python -c "import server"
server.py FAILS -> ModuleNotFoundError: No module named 'mcp.server.fastmcp'

$ pip install "mcp[cli]<2"      # resolves 1.29.1
$ python -c "import server"
[wiki] registered 3 topic tool(s) from .../mcp-wiki-server/wiki
server.py imports OK on 1.x
```

Both documented entry points hit this:

- `mcp-wiki-server/README.md:52` — `uv run --with "mcp[cli]" mcp dev server.py`,
  fully unpinned. (The `mcp dev` command itself still exists in 2.x, so the
  failure surfaces as an import error, not a missing command.)
- `.mcp.json.example` — `uv run --directory mcp-wiki-server python server.py`,
  which resolves the same unbounded `pyproject.toml` constraint.

**Recommendation — two separate steps, do not conflate them.**

1. *Now, zero risk:* cap the range.

   ```toml
   dependencies = ["mcp[cli]>=1.29.1,<2"]
   ```

   Breaking-change risk: **none.** It resolves to 1.29.1, which is the version
   the code was written against and which imports cleanly (verified above).
   The floor of 1.29.1 also carries the fixes in F2. Pin the README command
   the same way: `uv run --with "mcp[cli]<2" mcp dev server.py`.

2. *Separately, deliberately:* migrate to 2.x. Breaking-change risk: **high.**
   Upstream's 2.0.0 notes list `FastMCP` → `MCPServer`, `Client(cache=False)`
   → `cache=None` with a `CacheConfig()` default, `FileResource(is_binary=)` →
   `encoding`, removal of `Context.client_id` and of the `MCP_*` environment
   variables, and a narrowed `message_handler` contract. For this server the
   decorator API (`mcp.tool(name=...)`) is unchanged, so the migration is
   plausibly small — but it is a behaviour-bearing change and belongs in its
   own PR with the inspector run as evidence, not in a dependency bump.

---

### F2 — the `>=1.2` floor admits mcp versions with known advisories

**Severity: medium as a constraint; not exploitable in this deployment.**

Three reviewed advisories affect the `mcp` package:

| Advisory | CVE | Severity | Affected | Patched |
|---|---|---|---|---|
| GHSA-jpw9-pfvf-9f58 | CVE-2026-52869 | High | `<=1.27.1` (SSE since first release; Streamable HTTP since 1.8.0) | 1.27.2 |
| GHSA-hvrp-rf83-w775 | CVE-2026-52870 | High | `>=1.23.0, <=1.27.1`, only with `experimental.enable_tasks()` | 1.27.2 |
| GHSA-vj7q-gjh5-988w | CVE-2026-59950 | High | `<1.28.1`, deprecated WebSocket transport only | 1.28.1 |

None of them reach this server as it is written: `server.py:138` calls
`mcp.run()` with no transport argument, which is stdio, and all three
advisories are scoped to the HTTP, Streamable-HTTP, or WebSocket transports —
GHSA-vj7q-gjh5-988w states outright that "servers using stdio, SSE, or
Streamable HTTP are not affected." The task-handler issue additionally
requires an opt-in `enable_tasks()` call that this server never makes.

The finding is the *constraint*, not the current install: `>=1.2` lets a
resolver with a cache, a lockfile, or an offline mirror land on 1.27.1, and it
gives any future maintainer who adds an HTTP transport a silently vulnerable
floor. The F1 fix (`>=1.29.1,<2`) closes this in the same edit.

---

### F3 — `ruff==0.15.8` is 14 patch releases stale inside its own pinned line

**Severity: medium. Breaking-change risk of the fix: none (measured).**

`.github/workflows/ci.yml:21` pins `ruff==0.15.8`, released 2026-03-26. The
comment above it is accurate and worth keeping — 0.16.0 does ship stricter
defaults, and bumping the major line does belong with a lint-cleanup pass.
But the pin also freezes the repo five months inside the 0.15 line: 0.15.22
(2026-07-16) is the last release before 0.16.0.

Measured on this repo, all three versions run over the full tree:

| ruff | `ruff check .` |
|---|---|
| 0.15.8 (pinned) | All checks passed! |
| **0.15.22** | **All checks passed!** |
| 0.16.4 (current) | Found 46 errors (18 auto-fixable) |

**Recommendation:** bump to `ruff==0.15.22`. Breaking-change risk: **none** —
it is clean on this tree today, and it stays inside the boundary the existing
comment draws. Keep the comment; only the version number changes.

For whenever the 0.16 cleanup is scheduled, the 46 findings are already
scoped: `EXE001` ×18, `FURB167` ×7, `RUF100` ×4, `PLW1510` ×4, `I001` ×4,
`SIM117` ×2, `BLE001` ×2, and one each of `SIM114`, `SIM103`, `SIM102`,
`RUF059`, `PLC0206`, across 22 files. 18 are `--fix`-able and the `EXE001`
and `I001` bulk is mechanical, so the pass is smaller than the raw count
suggests — but it is a separate PR, and it would exceed this catalogue's
300-line budget.

---

### F4 — GitHub Actions are three majors behind

**Severity: medium. Breaking-change risk of the fix: low for this workflow.**

| Action | Pinned | Current major |
|---|---|---|
| `actions/checkout` | `@v4` | `@v7` (v7.0.1) |
| `actions/setup-python` | `@v5` | `@v7` |

Breaking changes on the path, checked against what `ci.yml` actually does:

- **Node 24 runtime** (setup-python v6, checkout v6/v7): requires runner
  ≥ 2.327.1. This workflow uses `runs-on: ubuntu-latest`, a GitHub-hosted
  runner, so this is satisfied automatically. Only a self-hosted runner would
  need attention.
- **ESM migration** (both v7 lines): internal to the actions, no workflow-side
  change.
- **`setup-python` v7 removed the `pip-install` input.** Not used here — the
  workflow calls `pip install` in its own `run:` steps.
- **`checkout` v7 blocks fork-PR checkout for `pull_request_target` and
  `workflow_run`.** Not used here — `ci.yml` triggers on `push` and
  `pull_request` only.

**Recommendation:** bump both to `@v7`. Nothing in this workflow touches a
removed input or a changed default, so the expected diff is two lines.

Worth deciding alongside it, but a separate call: neither action is pinned to
a commit SHA. Floating major tags are mutable, so a compromised tag is a
supply-chain path into CI. SHA-pinning costs readability and needs automation
to stay current — which is F5.

---

### F5 — no dependency automation at all

**Severity: medium.**

`.github/` contains only `workflows/ci.yml`. There is no
`.github/dependabot.yml`, no Renovate config, and no scheduled job that
checks for updates. Nothing in this repository would have told anyone that
`mcp` shipped a major release that breaks `server.py` — which is exactly how
F1 came to be, and why this manual audit is the mechanism of last resort.

**Recommendation:** add a `.github/dependabot.yml` covering three ecosystems:
`github-actions` (catches F4 and keeps SHA pins current if you adopt them),
`pip` on `/mcp-wiki-server` and `/skills/skill-creator`, and — since the ruff
pin lives in a `run:` line rather than a manifest — leave `ruff` to this
catalogue, which is the only surface Dependabot cannot see. Monthly is enough
for a repository of this size. Breaking-change risk: **none** — Dependabot
opens PRs, it does not merge them.

---

### F6 — the eval-suite's R dependencies are declared nowhere

**Severity: low-medium. Breaking-change risk of the fix: none (docs only).**

`eval-suite/` shells out to `Rscript` across four phases and its R sources
load eight packages:

`testthat` (×5), `jsonlite` (×4), `yaml` (×2), `data.table` (×2), `lintr`,
`digest`, `RSQLite`, `DBI`

None appear in a `DESCRIPTION`, a `renv.lock`, or an install command.
`eval-suite/README.md` (159 lines) has no prerequisites section — it names
`lintr` and `testthat` only in passing, while describing what the scoring
does. The external binaries are undeclared too: `Rscript`, the `opencode`
CLI the whole harness targets, `jq` (optional, guarded at `run.sh:118`), and
the judge CLI (guarded at `run.sh:64`).

`run.sh` has no preflight for any of the R packages — the two `command -v`
guards it does have cover only `$JUDGE_CLI` and `jq`. The failure mode is a
run that dies partway through with a bare R error, after the expensive
`opencode` calls have already been spent.

**Recommendation:** add a Prerequisites section to `eval-suite/README.md`
listing the eight packages as one `install.packages()` line plus the external
binaries, and add a preflight loop to `run.sh` that fails fast with the
missing names. `renv.lock` would additionally pin versions, but it is a much
heavier commitment for a harness whose whole point is running against a
moving model — recommend against it for now.

---

### F7 — `pyyaml>=6` and unbounded `hatchling`: no action

**Severity: informational.** Recorded so the next run does not re-derive it.

- **`pyyaml>=6`** — current release 6.0.3 (2025-09-25). All four advisories
  against PyYAML (CVE-2017-18342, CVE-2019-20477, CVE-2020-1747,
  CVE-2020-14343) are pre-6.0 deserialization issues, all fixed at or before
  6.0. No 7.x line exists, so the unbounded floor has no major to fall into.
  The one call site, `skills/skill-creator/scripts/quick_validate.py:74`, uses
  `yaml.safe_load`. Clean.
- **`hatchling`** (unbounded, `[build-system].requires`) — build-time only,
  and an unbounded backend requirement is the packaging norm. Current 1.32.0.
  No action.

## Summary

| # | Finding | Severity | Fix risk |
|---|---|---|---|
| F1 | `mcp[cli]>=1.2` unbounded; mcp 2.x removed `mcp.server.fastmcp` — install broken today | High | None for the cap; high for a 2.x migration |
| F2 | `>=1.2` floor admits mcp with 3 advisories (not exploitable on stdio) | Medium | None — same edit as F1 |
| F3 | `ruff==0.15.8`, 14 patches behind 0.15.22 | Medium | None — 0.15.22 verified clean |
| F4 | `checkout@v4`, `setup-python@v5`, three majors behind | Medium | Low — no removed input is used |
| F5 | No Dependabot/Renovate anywhere | Medium | None |
| F6 | eval-suite's 8 R packages and 4 binaries undeclared, no preflight | Low-med | None — docs + a guard |
| F7 | `pyyaml>=6`, `hatchling` unbounded | Info | No action |

Suggested order: F1 and F2 in one small PR (they are the same two lines and
the only finding that is broken right now), then F3 and F4 together as a CI
bump, then F5, then F6.

## Handed to other jobs

Noticed while auditing, out of scope for this job:

- `mcp-wiki-server/.mcp.json.example` hardcodes absolute paths
  (`/home/user/agents/mcp-wiki-server`) in both `--directory` and
  `WIKI_PATH`. → `security-footguns` (#6) and `doc-drift` (#2).
