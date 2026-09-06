# roomba — `dead-exports`, 2026-09-06

Baseline before the run: **green**, all 10 commands from *Baseline* in `ROOMBA.md`.
Output: 3 findings, 1 fixed in the catalogue, 2 report-only.

## Pre-stage: no tooling coverage

```console
$ scripts/roomba-scan.sh dead-exports
Hinweis: lokale ungenutzte Variablen und Imports sind Sache des CI-Gates.
Dieser Job behandelt nur Exporte ueber die Paketgrenze.
===== Pflichtbelege je Streichung =====
[checklist only, no candidates]
```

The scanner emitted its evidence checklist and **no candidate list**. This is the
root-only search documented in *Repository-specific notes on the pre-stages*: it keys off
`NAMESPACE` and `__all__` at the repository root, and this repository has neither. Per
that note the empty result is recorded as **no tooling coverage**, not as "nothing found".

The candidate list below therefore comes from the catalogue's own repo-specific analogue —
"skills present in `skills/` but not reachable via `skills.json`, a router, or
`.claude-plugin/`" — not from the scanner, and not from hand-searching.

## Finding 1 — `skills/skill-creator/` holds no source, only ignored bytecode — **report-only**

The one directory under `skills/` that no catalogue path reaches:

```console
$ ls -d skills/*/ | wc -l          # 24
$ python3 -c "…json.load(open('skills.json'))…"
skills.json count: 23
dirs not in skills.json: ['skill-creator']
skills.json not in dirs: []
```

Evidence chain per the job's required proofs:

| Proof | Result |
|---|---|
| `git ls-files skills/skill-creator` | **0 tracked files** |
| `git grep -l skill-creator` | only `ROOMBA.md` and `roomba/reports/2026-09-05-doc-drift.md` |
| `find skills/skill-creator -type f` | 12 files, **all `__pycache__/*.pyc`** |
| `git check-ignore` / `.gitignore` | `__pycache__/`, `*.pyc` → every file ignored |
| `git log -S` | removed by `ffe7cdc` (2026-09-01) "Remove guideline-distillation, skill-creator and zettelkasten skills" |
| dynamic use (`getattr`, registry) | none — no source remains to be called |

The directory is dead beyond doubt: the skill was removed cleanly from git five days ago,
and what survives on disk is orphaned Python bytecode from before the removal.

**No PR change.** Every file is gitignored, so deleting them produces a zero-line diff and
is a local-workspace cleanup, not a repository change:

```console
$ rm -rf skills/skill-creator      # recommended locally, changes nothing in git
```

The two sibling skills removed by the same commit, `guideline-distillation` and
`zettelkasten`, left no such directory — this is a one-off, not a pattern.

## Finding 2 — `ROOMBA.md` points `test-flakiness` at the removed skill — **fixed**

`ROOMBA.md` names `skills/skill-creator/tests` as a live test location in two places
(lines 107 and 120), written on 2026-09-05 — four days *after* `ffe7cdc` removed it.

This is the same object the 2026-09-05 `doc-drift` run examined. That run listed the
directory's three subdirectories and concluded:

> `ROOMBA.md` still points at `skills/skill-creator/tests` as a live test location, so the
> directory is not itself the error.

It stopped one level short. `skills/skill-creator/tests` contains **no tests** — it
contains `tests/__pycache__/*.pyc` and nothing else. The pointer that was taken as
evidence the directory is legitimate is itself the stale reference.

Consequence if left: the next `test-flakiness` run (job 5, never run) is sent to a
directory with no test files and would have to rediscover this before it could start.

Fixed by correcting both references to name only the test location that exists,
`eval-suite/`. Documentation only, no behaviour touched.

## Finding 3 — all 23 catalogued skills are reachable — **negative result**

Recorded so a later run need not redo it. Every skill in `skills.json` resolves through
one of the two permitted paths:

| Path | Count | Skills |
|---|---|---|
| direct plugin member (`plugins/*/skills/<name>`) | 12 | across all 6 plugins |
| router member | 11 | 9 under `skills/architecture/SKILL.md`, 2 under `skills/ai-ml/SKILL.md` |

`plugins/*/skills/<router>` is a symlink to `skills/<router>`, e.g.
`plugins/architecture/skills/architecture -> ../../../skills/architecture`; members ride
nested, which is why `check_docs.py` counts 21 and `check_plugins.py` counts 23. Both were
green in the baseline. No unreachable tracked skill exists.

## Scope note

CI already answers reachability conclusively for tracked skills — `build_routers --check`,
`check_docs.py` and `check_plugins.py` were all green and would have failed on an
unrouted tracked skill. Under the skill's *Abgrenzung* rule that makes finding 3 a
CI-gate question, not an agent question. What the gate cannot see is exactly what this run
found: a directory git no longer tracks. Worth weighing at the 2026-12-01 review whether
`dead-exports` should be narrowed to "untracked leftovers under `skills/`" or dropped.
