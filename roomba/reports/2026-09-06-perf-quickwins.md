# roomba — `perf-quickwins`, 2026-09-06

Baseline before the run: **green**, all 10 commands from *Baseline* in `ROOMBA.md`.
Output: 2 findings, 1 candidate measured and **rejected**, **0 changes**.

No pre-stage: this job has none. Every claim below carries a measurement or an
order-of-magnitude argument — per `references/jobs.md` §6, "looks slow" is not a finding
and does not appear here. Timings are medians on this machine, warm page cache.

**No PR.** Performance changes are behaviour changes until they are measured *and*
accepted; this job reports only.

## Finding 1 — `lcom.py` analyses git-ignored directories: 4.5 s and 607 KB of output where 115 ms and 8 reports are wanted — **high**

`skills/coupling-cohesion/scripts/lcom.py:444`:

```python
targets = sorted(path.rglob("*")) if path.is_dir() else [path]
```

`rglob("*")` descends into every directory, including the ones git is told to ignore.
Every surviving file is then fully parsed with `ast.parse`.

Measured on this working copy:

```console
$ lcom.py --json .                      4543 ms   1921 module reports   607 KB stdout
$ lcom.py --json scripts skills/refactoring/scripts
                                         115 ms      8 module reports
                                                            ratio: 40x
```

Where the work goes — 7072 paths walked, 1824 kept as "analysable source":

| Bucket | Files kept | Tracked by git? |
|---|---|---|
| `mcp-wiki-server/.venv/…` (site-packages) | 1271 | no — `.venv/` is in `mcp-wiki-server/.gitignore` |
| `.worktrees/71-validate-eval-set/…` (a duplicate checkout) | 517 | no — `/.worktrees/` is in `.gitignore` |
| genuine first-party source | ~36 | yes — the repo has **13** tracked `*.py` files |

95 % of the walked paths sit under a dot-directory. Pruning dot-directories from the walk
alone: **103.4 ms → 2.9 ms, 35.8x**, and the file count drops from 1824 to 36.

This is not only a speed problem. The `coupling-cohesion` skill and its `cohesion-analyst`
subagent consume this output: 607 KB of JSON, dominated by third-party `site-packages`
modules and by a second copy of this repository, is a cohesion report about someone else's
code. A developer checkout with a virtualenv or a node_modules is the normal case for the
tool's intended users, so this is not an artefact of this machine.

**Suggested fix** (behaviour change — not applied): prune dot-directories during the walk
and, where the target is a git work tree, filter through `git check-ignore` or
`git ls-files`. It changes which modules appear in the output, which is exactly why it does
not belong in a roomba PR.

## Finding 2 — the wiki listing reads every page in full to print its first line — **medium, conditional**

`mcp-wiki-server/server.py:88-91` builds the page index like this:

```python
first = next((ln for ln in f.read_text(...).splitlines() if ln.strip()), "")
```

`read_text()` loads the whole file before `next()` takes the first non-blank line, so the
cost is O(total bytes) where O(first line) suffices. Streaming the open file handle instead
gives identical output — verified by asserting equality across both corpora below.

| Corpus | whole-file | first-line | ratio |
|---|---|---|---|
| shipped sample (3 pages, 2.5 KB total) | 0.019 ms | 0.016 ms | 1.2x |
| 40 pages × 20 KB | 2.54 ms | 0.71 ms | 3.6x |
| 40 pages × 500 KB | 79.13 ms | 0.67 ms | **118x** |

The first-line cost is flat in page size; the current cost is not. On the bundled demo wiki
this is worth nothing, which is why the finding is conditional — but `resolve_wiki_root()`
clones an arbitrary wiki from `WIKI_GIT_URL`, and this runs on every listing call of a
served MCP tool. Fix it when a real corpus is attached, not before.

The query branch at `:76` also reads whole files, but a text search genuinely needs the
content; only its memory profile, not its complexity, would improve from streaming.

## Measured and rejected — `check_plugins.py` reads each `SKILL.md` three times

Recorded so the next run does not re-open it. `skill_categories()`, `skill_activations()`
and `claude_skills()` (`:39`, `:49`, `:59`) each iterate every skill directory and each call
`read_text()`, so all three are called per run (`:156`, `:157`, `:166`) and the 238 KB
corpus is read three times over.

A single-pass rewrite was implemented and asserted to return identical results:

```
three passes : 6.45 ms
single pass  : 4.23 ms
saving       : 2.22 ms  (34 % of the read phase, 4.2 % of the 53 ms run)
```

34 % sounds like a win; 2.2 ms is not one. Interpreter startup dominates the command. **Not
reported as a finding** — this is the "merely ugly" case the job's rule exists to exclude.

## Examined and clean

| Site | Why it is not a finding |
|---|---|
| `skills/refactoring/scripts/churn.py` | the obvious N+1 (one `git log` per file) is absent by design — `run_git` is called exactly three times per run, one of them the single `git log` pass its docstring promises |
| `eval-suite/run.sh` | no per-item subprocess beyond the one agent call each task requires; directory listing sorted once |
| `coupling_metrics.py`, `balance_check.py` | single JSON read, then in-memory work over an edge list |
