# ROOMBA job 4 — `error-edges`

**Date:** 2026-08-27 · **Output:** report only (no code changed) ·
**Scope:** every first-party Python, Bash and R file in the repo — `scripts/`,
`install.sh`, `mcp-wiki-server/`, `eval-suite/`, and the scripts shipped inside
`skills/`.

The job looks for two shapes: an IO or process boundary with no error handling
at all, and a boundary whose error is caught and then thrown away. Nine
findings, ordered by how badly the failure misleads whoever hits it. Each was
reproduced against a scratch copy of the tree at `6181c31`; the exact
reproduction is given per finding.

Two of them (F1, F8) are cases where a *deliberately written* error message
never reaches the person it was written for. Those are the ones worth fixing
first: the diagnosis already exists, it just does not come out.

---

## F1 — `build_manifest.py`'s validation messages arrive as tracebacks

`scripts/build_manifest.py:170-233` (`build_entry`) raises `ValueError` with
carefully worded messages — `frontmatter missing 'description'`, `description
is 1103 chars (limit 1024; longer skills are dropped by Claude.ai)`, `'category'
must be one of …`, `'targets' has unknown value(s) …`, and the strict-YAML
check's `unquoted 'description' value contains ': ' — invalid YAML; rephrase
(e.g. use an em-dash) or quote the value`.

`main()` (line 245) calls `build_manifest()` with no `try`. Every one of those
messages is delivered as an unhandled exception.

Reproduced — dropping `description:` from `skills/adr-workflow/SKILL.md` and
running `python3 scripts/build_manifest.py --check`:

```
  File ".../scripts/build_manifest.py", line 245, in main
    skills = [build_entry(p) for p in find_skill_files()]
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File ".../scripts/build_manifest.py", line 188, in build_entry
    raise ValueError(f"{skill_md}: frontmatter missing 'description'")
ValueError: .../skills/adr-workflow/SKILL.md: frontmatter missing 'description'
```

This is the CI step named **"Manifest in sync"**. A contributor adding a skill
sees a stack trace where the repo's other five checks all print a one-line
`… drift detected:` block and a "here is what to do" sentence. The information
is there — it is just buried under six frames of `pathlib` and a list
comprehension.

**Suggested fix.** Wrap the body of `main()` in
`except ValueError as exc: sys.stderr.write(f"error: {exc}\n"); return 1`.
Four lines; the messages are already written.

## F2 — `build_routers.py`: same, plus a corrupt manifest raises raw JSON errors

`scripts/build_routers.py` raises tailored `ValueError`s in `routed_categories()`
(`a router's name (…) must equal its category (…)`) and `splice_region()`
(`missing or malformed generated-members markers`). `main()` collects only the
`errors` list its helpers *return*; anything they *raise* escapes.

On top of that, `load_members()` (line 71) calls
`json.loads(MANIFEST_PATH.read_text(…))` unguarded. `skills.json` is a
generated file, so a half-written one is a real state — an interrupted
`build_manifest.py` leaves exactly that.

Reproduced — `skills.json` replaced with `{ not json`, then
`python3 scripts/build_routers.py --check`:

```
json.decoder.JSONDecodeError: Expecting property name enclosed in double
quotes: line 1 column 3 (char 2)
```

No mention of `skills.json`, and no hint that `build_manifest.py` regenerates
it.

**Suggested fix.** Same `except ValueError` wrapper in `main()`, plus catching
`json.JSONDecodeError` in `load_members()` and re-raising as
`ValueError(f"{MANIFEST_PATH}: invalid JSON ({exc}); run build_manifest.py")`.
Note `check_plugins.py:81` already does exactly this for `marketplace.json` —
the pattern exists in the repo, it just is not applied here.

## F3 — `check_descriptions.py` aborts on the first malformed file

`scripts/check_descriptions.py:52-54` reads each `SKILL.md` and hands it to
`extract_frontmatter`, which raises `ValueError("missing opening '---'
frontmatter delimiter")` for a file with no frontmatter.

The surrounding loop is built to *accumulate*: it appends to `errors` for a
missing description and keeps going, so the author sees every problem at once.
A malformed file breaks that contract — the loop dies at the first one, and the
skills after it are never checked.

Reproduced — replacing `skills/ddd/SKILL.md` with a line of plain prose:

```
  File ".../scripts/build_manifest.py", line 63, in extract_frontmatter
    raise ValueError("missing opening '---' frontmatter delimiter")
ValueError: missing opening '---' frontmatter delimiter
```

The message also names no file, because `extract_frontmatter` takes only the
text. The caller knows the path; the raiser does not.

**Suggested fix.** `try/except ValueError` around the parse inside the loop,
appending `f"{skill_md.parent.name}: {exc}"` to `errors` and `continue`-ing.
That restores the accumulate-and-report behaviour the rest of the function
already has.

## F4 — `render()` in the wiki server: one broken symlink takes out a whole topic

`mcp-wiki-server/server.py:69-95`. The `page=` branch is guarded — it checks
`target.is_relative_to(base)` and `target.is_file()` before reading. The other
two branches are not:

```python
files = sorted(topic.rglob("*.md"))          # matches dangling symlinks too
...
for f in files:
    for i, line in enumerate(f.read_text(...).splitlines(), start=1):
```

`errors="replace"` covers a decode failure but says nothing about `OSError`. A
`*.md` symlink whose target is gone still matches `rglob` (glob matches on the
name), and `read_text` then raises.

Reproduced — a topic containing one good page and `broken.md -> missing-target.md`:

```
render(topic, None, None)  -> FileNotFoundError: 'wt3/topic/broken.md'
render(topic, 'ok', None)  -> FileNotFoundError: 'wt3/topic/broken.md'
```

Both the table-of-contents call and *every* search on that topic fail. The good
page is never listed. For a git-backed wiki (`WIKI_GIT_URL`) this is not
hypothetical — a symlink to a file dropped in a later commit is an ordinary
repository state, and the same race exists for any file deleted between the
`rglob` and the read.

**Suggested fix.** A small `read_page(f) -> str | None` helper returning `None`
on `OSError`, used by both loops; skip the file and note the count. The
consistency argument is strong here — the `page=` branch already decided that
an unreadable page is a *result*, not a crash.

## F5 — a failed clone kills the wiki server at import time

`mcp-wiki-server/server.py:33-52`. The refresh path is deliberately
best-effort:

```python
if refresh.returncode != 0:
    detail = refresh.stderr.decode("utf-8", errors="replace").strip()
    print(f"[wiki] refresh failed, serving cached copy: {detail}", file=sys.stderr)
```

The clone path, three lines below, is the opposite:

```python
subprocess.run(["git", "clone", "--depth", "1", "-b", branch, "--", url, str(cache)],
               check=True)
```

`check=True` with no `capture_output`, called at module scope through
`register_topics(resolve_wiki_root())` (line 138). A wrong `WIKI_GIT_URL`, a
branch that does not exist, no network, or expired credentials all raise
`CalledProcessError` before a single tool is registered, and the MCP client
gets a traceback rather than a line naming the URL and branch it tried.

`register_topics` itself handles both of its own bad states politely (`[wiki]
root not found:`, `[wiki] no topic folders in`) — so the module already has a
house style for startup problems; the clone just does not follow it.

**Suggested fix.** `capture_output=True`, drop `check=True`, and on a non-zero
return code print `[wiki] clone failed ({url}@{branch}): {stderr}` and fall
back to `WIKI_PATH` — or exit with that message. Either beats a traceback.

## F6 — `install.sh` converts agents behind a `except Exception: sys.exit(1)`

`install.sh:497-573`. `plugin_agent_toml()` runs an embedded Python that parses
an agent's frontmatter, and ends:

```python
except Exception:
    sys.exit(1)
```

The caller (line 590-593) prints:

```
  WARN      failed to convert <path> (skipping)
```

Nothing else. A missing `name:`, a missing `description:` (`KeyError`), an
empty body, absent frontmatter, and a genuine bug in the converter are all the
same output. Neither `sys.exit(1)` nor the WARN carries the exception.

Reproduced — `plugins/architecture/agents/coupling-analyst.md` with its
`description:` removed, then `./install.sh --target=codex --category=architecture`:

```
  agent     cohesion-analyst -> .../.codex/agents/cohesion-analyst.toml
  WARN      failed to convert .../coupling-analyst.md (skipping)
  skills    9 routed members disabled in .../.codex/config.toml
```

`echo $?` → **0**. The install reports success; one of the two subagents the
README promises is simply not there, and the reason (`KeyError: 'description'`)
was computed and discarded.

Worth noting the repo already validates this exact frontmatter —
`scripts/check_plugins.py:check_agents()` checks `name` and `description` and
reports precisely. So CI would catch a committed regression; the gap is what a
*user* sees when it happens to them, e.g. against a locally edited agent.

**Suggested fix.** Replace `except Exception: sys.exit(1)` with
`except Exception as exc: print(f"{type(exc).__name__}: {exc}", file=sys.stderr);
sys.exit(1)` — stderr is already inherited, so the reason lands next to the
WARN with no other change.

## F7 — `eval-suite/run.sh` continues after `setup.R` fails, having discarded why

`eval-suite/run.sh:154-158`:

```bash
if [[ -f "$task_dir/setup.R" ]]; then
  (cd "$work" && Rscript "$task_dir/setup.R" >/dev/null 2>&1) || {
    echo "  setup.R failed" >&2
  }
fi
```

`2>&1` to `/dev/null` throws away R's error before the `||` can report it, so
the message has no reason attached. The run then proceeds: the model is asked
to work on input data that was never created, produces something that cannot
pass, and `score.R` records an ordinary test failure.

The consequence is in the output, not the console. A broken `setup.R` and a
model that genuinely failed the task are **indistinguishable in
`results.csv`** — and comparing configs is the entire purpose of the harness. A
setup break in one task quietly moves the A/B delta.

**Suggested fix.** Capture into `$out_dir/setup.stderr` instead of `/dev/null`,
print the first line with the warning, and record `setup_failed: true` in
`meta.json` so `aggregate.R` can exclude the task rather than score it. The
harness already writes `opencode.stdout`/`opencode.stderr` per run — this is
the same treatment for the one step that currently gets none.

## F8 — subprocess timeouts nobody catches

Three call sites give a model CLI a timeout and then let `TimeoutExpired`
escape:

- `eval-suite/recall/check_recall.py:104-109` — `timeout=120` per prompt.
  `score()` loops over every prompt, and `main()` runs the flat menu fully
  before starting the routed one. One slow call at prompt 18 of 20 throws away
  the 17 completed model calls before it *and* the entire flat half of the A/B.
  The script's own docstring establishes the opposite instinct for the other
  failure mode: "If it is absent, the check skips with a clear message instead
  of failing, so CI without model access stays green."
- `skills/skill-creator/scripts/utils.py:155-168` (`coder_cli_invoke`) —
  `timeout=timeout` (default 300). The two neighbouring failure modes are
  handled with care: `FileNotFoundError` gets `$CODER_CLI={backend!r} requires
  {cmd[0]!r} on PATH`, and a non-zero exit gets `{backend} (…) exited {rc}` plus
  stderr. A timeout gets a bare `subprocess.TimeoutExpired` naming an argv the
  caller never assembled.
- `skills/skill-creator/scripts/run_eval.py:147,307` — `select.select(…, 1.0)`
  polling loops around the same CLI.

**Suggested fix.** In `coder_cli_invoke`, `except subprocess.TimeoutExpired as
exc: raise RuntimeError(f"{backend} timed out after {timeout}s") from exc` — one
line, and it matches the two messages already there. In `check_recall.py`,
count a timeout as a miss and carry on; a partial A/B with one recorded timeout
is worth more than no A/B.

## F9 — `churn.py` reports unreadable files as deleted

`skills/refactoring/scripts/churn.py:224-236`:

```python
def measure(root: Path, entry: FileChurn) -> None:
    target = root / entry.path
    try:
        if not target.is_file():
            return
        data = target.read_bytes()
    except OSError:
        return
    entry.exists = True
```

An `OSError` leaves `exists = False`, and `main()` (line 415) then folds the
file into `dropped_missing`, which `render()` prints as:

```
143 files ranked since 12 months ago (7 gone from the tree, not shown)
```

A file that exists but could not be read is counted as one that was deleted.
The script's docstring is explicit that the dropped set means "there is nothing
left to refactor" — for an unreadable file that is the wrong conclusion, and a
directory the user cannot traverse silently removes a whole subtree from the
ranking.

The size of this depends on the caller: run over a repo containing a
root-owned build directory, or an SMB/NFS mount with a stale handle, the
"gone from the tree" number is quietly wrong.

**Suggested fix.** A third state — `entry.unreadable = True` — counted and
rendered separately (`3 unreadable`). Roughly six lines, and it keeps the
existing docstring true.

---

## Boundaries checked and found sound

Recorded so a later run does not re-litigate them:

- `scripts/check_plugins.py` — `marketplace.json` and every `plugin.json` are
  read inside `try/except json.JSONDecodeError` with a message naming the file
  (lines 81, 103); `readlink` results are compared, never dereferenced. This is
  the model the other four scripts should follow.
- `skills/skill-creator/scripts/utils.py:load_eval_set` — `OSError` and
  `JSONDecodeError` are both converted to `EvalSetFormatError` naming the path,
  so callers report one kind of failure. Exemplary.
- `skills/refactoring/scripts/churn.py:run_git` — `FileNotFoundError` becomes
  `GitError("git is not installed or not on PATH")`, non-zero exits carry git's
  own stderr, and `main()` catches `GitError` for a clean `error: …` line.
- `mcp-wiki-server/server.py` `page=` traversal guard — `target.resolve()` then
  `is_relative_to(base)` where `base` is `topic.resolve()`, so a symlinked
  directory inside a topic cannot be used to escape. Verified against a
  `topic/linked -> ../../outside` symlink: `page=linked/private.md` returns
  `Page not found`, and on CPython 3.11 `rglob` does not descend into it either.
- `install.sh` marker handling — `mcp_markers_balanced` and
  `skill_override_markers_balanced` both refuse to touch a config with a
  dangling marker rather than truncating it, and `write_codex_config` writes via
  a temp file plus `mv`. The dangerous path here is already the careful one.

## What this run did not do

Report-only by catalogue rule, so no code changed. Nothing here needs a
behavioural decision — F1, F2, F3, F6 and F8 are each a handful of lines that
surface a message the code already computes.

If one is worth a follow-up PR first, it is **F1 + F2 + F3**: three `main()`
wrappers that turn the repo's most-hit CI failure mode from a stack trace into
the sentence it was meant to be.
