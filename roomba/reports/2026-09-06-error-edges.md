# roomba — `error-edges`, 2026-09-06

Baseline before the run: **green**, all 10 commands from *Baseline* in `ROOMBA.md`.
Output: 3 findings, **0 changes** — every fix here changes behaviour, so this job never
produces a code diff (`references/jobs.md` §4).

Surface examined: all 13 tracked `*.py` and 4 tracked `*.sh` files. Every `try`/`except`
in the repository was read (18 handlers across 8 files), plus every `subprocess` call site
(5) and the `set -` line of every shell script.

**No bare `except:` and no `except Exception: pass` exists in this repository.** Every
handler catches a named type. The findings below are the narrower cases: results that are
never examined, and failures that end in exit code 0.

## Finding 1 — `check_live.py` cannot distinguish a broken CLI from a real miss — **high**

`eval-suite/recall/check_live.py:120`:

```python
result = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=600)
# A max-turns exit is expected and still carries the events we need.
return result.stdout.splitlines()
```

`result.returncode` and `result.stderr` are never read — `grep -n "returncode" check_live.py`
returns nothing. The comment justifies ignoring *one* nonzero exit (max-turns); the code
ignores *all* of them.

Its sibling in the same directory, `check_recall.py:110`, makes the identical call and
handles it correctly:

```python
if result.returncode != 0:
    raise RuntimeError(result.stderr.strip() or "claude CLI failed")
```

**Impact, demonstrated:** on a nonzero exit `stdout` is empty, `observe()` iterates zero
lines, and the result is byte-identical to a genuine routing miss.

```console
$ python3 -c "…from check_live import observe…"
failing CLI -> returncode: 1 | stdout lines: []
observe(failed run)   -> (False, None)
observe(genuine miss) -> (False, None)
```

An auth failure, a rate-limit rejection or a crashed session is therefore reported as
*"the router did not fire"* — a tool failure rendered as a measurement result. This is not
hypothetical: open issue **#95** documents the same class of outcome in the (since removed)
skill-creator harness — *"runs to completion but reports recall = 0% … the numbers look
like a catastrophically bad description; in fact nothing was measured"* — and its cause 3
records `claude -p` exiting 1 under parallel load, which is exactly the input that makes
this path silent.

`FileNotFoundError` (no `claude` on `PATH`) is not affected: it propagates uncaught.
The silent case is specifically a nonzero exit.

**Suggested fix** (behaviour change — not applied): adopt the sibling's check, exempting
only the max-turns exit the comment names, and let every other nonzero exit raise with
`stderr` attached.

## Finding 2 — `roomba-scan.sh dead-exports` reports nothing and success when it ran nothing — **medium**

`scripts/roomba-scan.sh`, `dead-exports` branch: both bodies are guarded by
`if is_r_pkg && has Rscript` and `if is_python`, and **neither guard has an `else skip …`**.
Where both are false — as in this repository, which has no root `DESCRIPTION`,
`pyproject.toml` or `requirements.txt` — the branch prints its checklist, runs no probe,
and exits 0:

```console
$ scripts/roomba-scan.sh dead-exports >/dev/null 2>&1; echo $?
0
```

The output carries no `[uebersprungen]` marker, so "scanned, found nothing" and "never
scanned" are the same bytes on stdout and the same exit code. The file's own `deps-audit`
branch does this right — `skip "renv.lock oder Rscript fehlt -> renv::vulns()"` — and the
`test-flakiness` branch at least prints `kein tests/ oder test/ Verzeichnis gefunden`.
The `dead-exports` branch is the one that stays silent.

**Impact:** the catalogue already pays for this. `ROOMBA.md` carries a prose rule telling
every run to read an empty pre-stage as "no tooling coverage", not "nothing found" — a
human-memory workaround for a missing `skip()` call. Two runs have now been tripped by it
(`deps-audit` 2026-09-05, `dead-exports` 2026-09-06); had the 2026-09-05 run trusted the
silence, it would have missed the `mcp[cli]` bound it rated its second-most-severe finding.

`set -uo pipefail` without `-e` is deliberate and correct here — a scanner should run every
probe even when one fails — and is not itself the finding.

**Suggested fix** (behaviour change — not applied): add the two `else skip …` arms so the
absence of a probe is stated, not inferred. Belongs with the scanner rework already in
*Backlog*.

## Finding 3 — `lcom.py` returns 0 after dropping files from the metric — **low**

Two paths remove a file from the analysis and let the run report success:

- `:133` `except SyntaxError` → warns to stderr, `return []` — an unparseable file is
  excluded from the metric.
- `:500` a nonexistent input path → warns to stderr, `continue`.

`main()` then `return 0` unconditionally (`:513`), and the `--json` payload is built only
from files that survived — it has no field recording what was skipped:

```console
$ python3 skills/coupling-cohesion/scripts/lcom.py --json ./no-such-dir
warning: no such path: no-such-dir
[]
exit=0
```

A caller that checks the exit code, or consumes the JSON without also reading stderr, sees
a successful cohesion analysis over an empty file set. The warnings are real, so this is
`warning` where the computation continues rather than a fully silent swallow — hence low,
not high. `balance_check.py:200` and `coupling_metrics.py:181` in the same directory both
`return 1` on bad input, so the inconsistency is inside one skill.

**Suggested fix** (behaviour change — not applied): a nonzero exit when a requested path
resolved to nothing, and a `skipped` key in the JSON payload.

## Examined and clean

Recorded so a later run need not re-read them:

| Site | Why it is not a finding |
|---|---|
| `mcp-wiki-server/server.py:38` | fetch failure evaluated, logged to stderr with detail, degraded behaviour documented in a comment; the clone at `:47` uses `check=True` |
| `skills/refactoring/scripts/churn.py` | `run_git` checks `returncode` and raises `GitError` with `stderr`; `has_commits`/`parse_iso`/`measure` catch deliberately and return a documented sentinel |
| `scripts/check_plugins.py:80,102` | both handlers append to `errors`, which drives a nonzero exit |
| `scripts/quick_validate.py:83` | `yaml.YAMLError` reported, not swallowed |
| `coupling_metrics.py`, `balance_check.py` | `FileNotFoundError`/`JSONDecodeError` → `InputError` → `return 1` |
| `check_live.py:136` | `except json.JSONDecodeError: continue` over stream-json lines — non-JSON lines are expected noise in that format |
| `install.sh`, `test_install.sh`, `eval-suite/run.sh` | all `set -euo pipefail` |
