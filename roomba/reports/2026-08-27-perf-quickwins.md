# ROOMBA job 7 — `perf-quickwins`

**Date:** 2026-08-27 · **Output:** report only · **Scope:** `install.sh`,
`scripts/`, `mcp-wiki-server/`, `eval-suite/`, `.github/workflows/ci.yml`.

Six findings. Every number below was measured on this machine against
`6181c31` — best-of-7 for wall clock, and exact counts for IO, obtained by
patching `pathlib.Path.read_text` and by shimming `grep` on `PATH`.

**Read the severity honestly.** Only two of these six are worth acting on for
speed. The repo's Python checks all run in about 30 ms, and most of that is
interpreter startup — their read amplification is real but it costs nothing
you can feel at 25 skills. Those are reported as scaling and clarity notes, not
as wins. F1 and F2 are the ones with weight behind them.

| # | Where | Measured | Worth doing? |
|---|---|---|---|
| F1 | `install.sh` | 219 `grep` forks, **384 ms of an 875 ms run** | **Yes** |
| F2 | `mcp-wiki-server/server.py` | **504× read amplification** on the table-of-contents path, per call | **Yes** |
| F3 | `.github/workflows/ci.yml` | 25 Python startups, **1055 ms**, for ~300 ms of work | Yes, cheap |
| F4 | `scripts/check_plugins.py` | 75 reads of 25 files (3×) | Scaling note |
| F5 | `scripts/check_docs.py` | 48 reads of 25 files (2×) | Scaling note |
| F6 | `build_routers.py`, `check_recall.py` | re-parse / linear scan | Clarity note |

---

## F1 — `install.sh` forks a `grep` per frontmatter field, per skill, per target

Five helpers each answer one question by launching a process against the same
file:

```bash
skill_environments()      grep -m1 '^environments:' "$skill_md"
skill_targets()           grep -m1 '^targets:'      "$skill_md"
skill_activation()        grep -m1 '^activation:'   "$skill_md"
skill_category()          grep -m1 '^category:'     "$skill_md"
skill_matches_category()  grep -m1 '^category:'     "$skill_md"
```

Nothing caches. `list_skills()` calls two of them per skill; `routed_categories()`
calls two more per skill and is invoked afresh; and the main loop calls
`skill_activation` and `skill_category` again for **every (target, skill)
pair** — 3 targets × 25 skills × 2 = 150 on their own.

Measured by putting a counting shim ahead of `grep` on `PATH` and running
`./install.sh --target=all --dry-run`:

```
grep invocations: 219
```

Attribution — 219 forks of the same command, against the cost of answering the
same question in-process:

```
219 grep forks alone: 384ms
219 in-process reads:   3.3ms
```

The whole `--target=all --dry-run` run takes **875 ms**, so process creation for
these greps is **44% of it**, and it grows as *skills × targets*. Every one of
the 219 reads the same handful of files; a skill's frontmatter cannot change
mid-run.

**Suggested fix.** One pass at startup filling an associative array keyed by
`"$skill:$field"` — a single `awk` over `skills/*/SKILL.md` emitting
`skill<TAB>field<TAB>value` for the five fields, read into the map with a
`while read` loop. The five helpers become array lookups and keep their
signatures, so nothing else in the script changes. Bash 4 associative arrays
are already assumed elsewhere in the file's style, and `test_install.sh` covers
the behaviour end to end, so the refactor has a net under it.

Second-order note: `install.sh` deliberately avoids `sort`/`wc`/`tr` "so it
works under the minimal sandboxed PATH" (comment at
`install_codex_member_overrides`). `awk` is already used for the four marker
filters, so this adds no new dependency.

## F2 — the wiki table of contents reads every page in full to take one line

`mcp-wiki-server/server.py:87-95`:

```python
lines = [f"# {topic.name} pages", ""]
for f in files:
    first = next(
        (ln for ln in f.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()),
        "",
    )
    lines.append(f"- `{f.relative_to(topic)}` — {first[:100]}")
```

`read_text()` pulls the whole file into memory and `splitlines()` materialises
every line, so that `next()` can take the first non-blank one and truncate it to
100 characters. This is the **no-argument** call — the one an agent makes to
find out what a topic contains, i.e. the cheapest-looking and most frequent one.

Measured against a realistic corpus (this repo's own `skills/**/*.md`, 61 pages
of hand-written documentation — the shape a knowledge base actually has):

```
61 markdown pages, 523,633 bytes on disk
table-of-contents needs the first non-blank line of each: 1,038 bytes
render() reads all 523,633 bytes -> 504x amplification
```

Half a megabyte read and split, per call, to produce a kilobyte. There is no
cache: `render()` is called fresh on every tool invocation, and `MAX_PAGE_CHARS`
does not apply here — it only guards the `page=` branch.

**Suggested fix.** Iterate the file object and stop:

```python
def first_line(path: Path) -> str:
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.strip():
                return line.strip()
    return ""
```

Reads one buffer instead of the file. Same output. This also composes with the
`error-edges` job's F4 (an unreadable page currently raises out of this exact
loop) — one helper can fix both, returning `""`/`None` on `OSError`.

The `query=` branch below it genuinely has to read everything, so it is not part
of this finding — though it would inherit the same helper, and its early `break`
at `MAX_QUERY_HITS` already stops the outer loop correctly.

## F3 — CI spends a second launching Python 25 times to validate 25 files

`.github/workflows/ci.yml:44-56`:

```yaml
for d in skills/*/; do
  [ -f "$d/SKILL.md" ] || continue
  python3 skills/skill-creator/scripts/quick_validate.py "$d" >/dev/null || {
    echo "::error file=${d}SKILL.md::$(python3 skills/skill-creator/scripts/quick_validate.py "$d" 2>&1)"
    fail=1
  }
done
```

Measured:

```
25 quick_validate.py invocations (the CI loop): 1055ms -> 42ms each
bare `python3 -c pass`:                           11ms
```

Roughly 275 ms of interpreter startup plus the `pyyaml` import repeated 25
times, for work that is a few milliseconds per file. And a *failing* skill costs
double: the script is run a second time inside the `$(…)` just to recover the
message the first run already printed and `>/dev/null` discarded.

**Suggested fix.** Two independent, small changes:

- Capture once instead of running twice:
  `out="$(python3 … "$d" 2>&1)" || { echo "::error file=${d}SKILL.md::$out"; fail=1; }`.
  Strictly better — fewer runs and no risk of the two invocations disagreeing.
- Longer term, teach `quick_validate.py` to accept several directories and
  report per-file, turning 25 startups into one. Its `main()` already loops over
  checks; accepting `sys.argv[1:]` is a small change, and the step comment's
  intent ("only running it proves its allowlist still matches") is preserved.

## F4 — `check_plugins.py` reads every `SKILL.md` three times

`skill_categories()`, `skill_activations()` and `claude_skills()` each walk
`SKILLS_DIR`, read every `SKILL.md`, and run one regex — for `category:`,
`activation:` and `targets:` respectively. Three passes over the same 25 files
for three fields of the same frontmatter block.

Measured by patching `pathlib.Path.read_text` and running `main()`:

```
check_plugins   total read_text=  84  SKILL.md reads=  75 over 25 files
```

Exactly 3× per file; the worst individual file is read three times.

**Honest severity:** the script runs in **31.5 ms** (best of 7), most of it
interpreter startup. This is not a speed problem today. It is worth noting
because the three functions are near-identical copies that will drift — and
because `check_docs.py` (F5) has grown its own copy of two of them.

**Suggested fix.** One `load_skills() -> dict[str, SkillMeta]` pass returning a
small dataclass with `category`, `activation`, `targets`; the three functions
become one-line projections over it. Consolidates the duplicated regexes as a
side effect.

## F5 — `check_docs.py` reads every `SKILL.md` twice

Same shape, one pass smaller: `skill_names()` reads each file to skip routers,
then `skill_categories()` re-reads the survivors for `category:`.

```
check_docs      total read_text=  50  SKILL.md reads=  48 over 25 files
```

(48 rather than 50 because the two routers are read once and dropped.) Runs in
**26.4 ms**. Same verdict as F4: fold into one pass when touching the file, not
as its own change.

Note that `check_docs.py`, `check_plugins.py` and `install.sh` now each carry
their own `category:` / `activation:` / `targets:` regex or grep. That is four
implementations of "parse this frontmatter field", and `build_manifest.py`
already exports a real parser (`extract_frontmatter` / `parse_frontmatter`)
that `check_descriptions.py` and `build_routers.py` both import. The two
`check_*.py` scripts could import it too and delete their regexes.

## F6 — two small re-computations

**`build_routers.py:71` re-reads and re-parses `skills.json` per category.**
`load_members()` opens and `json.loads` the whole manifest on every call, and
`process()` calls it once per routed category:

```
build_routers   skills.json reads = 2
```

Two today, one per routed category as more get flipped. Hoist the parse into
`main()` and pass the list down. The script runs in 31.9 ms; this is a clarity
fix that happens to remove work.

**`check_recall.py:58-62` scans the skill list per lookup.** `category_of()` is
a linear walk over all skills, called once per prompt during `--category`
filtering and again per prompt inside `score()`'s routed pass — O(prompts ×
skills). With 20 prompts and 25 skills it is invisible; as a dict built once in
`main()` it is also simply shorter. Worth folding in whenever that file is next
touched.

---

## Checked and found fine

Recorded so a later run does not re-open them.

- **No N+1 over subprocesses in the Python tooling.** The only
  `subprocess.run` calls in `scripts/` are none; `churn.py` makes exactly one
  `git log` call for the whole window (its docstring calls it "One `git log`
  pass") plus `rev-parse` twice for setup, which is the right shape.
- **`churn.py:measure()` reads each file once** into `bytes` and derives both
  the binary sniff and the line count from that one buffer — no re-read, no
  decode.
- **`eval-suite/run.sh`'s per-task work is dominated by the model call**, not by
  the harness. The `jq` calls on `opencode.json` run once per (config, task)
  and could be hoisted, but against a multi-second CLI invocation it is noise.
- **`lcom.py` and `coupling_metrics.py`** parse each input file once (`ast.parse`
  / one regex sweep) and reuse the tree. No repeated parsing.
- **The `skills.json` manifest is read once** by `check_descriptions.py` and
  `check_recall.py` — only `build_routers.py` (F6) re-reads it.

## What this run did not do

Report-only. Nothing changed.

If one follow-up PR is worth doing, it is **F1** — it is the only finding where
the fix removes a measurable, growing cost (44% of `install.sh`'s wall clock,
scaling as skills × targets) and `test_install.sh` already covers the behaviour
being preserved. **F2** is second: smaller in absolute terms today but it is a
running server, the amplification is per-call, and the fix is a six-line helper
the `error-edges` job independently wants for a different reason. **F3**'s
first half (capture once instead of running twice) is a two-line CI edit worth
taking along with whatever else touches that workflow.

F4 through F6 should ride along with unrelated work on those files. Turning
them into their own PR would be motion, not improvement.
