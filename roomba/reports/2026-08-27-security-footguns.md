# ROOMBA job 6 — `security-footguns`

**Date:** 2026-08-27 · **Output:** report only — this job never patches, by
catalogue rule · **Scope:** `install.sh`, `scripts/`, `mcp-wiki-server/`,
`eval-suite/`, `.github/workflows/`, and the scripts shipped inside `skills/`.

Seven findings. Two of them (F1, F2) are exploitable as written and were
reproduced against a scratch copy of `6181c31`; the rest are unsafe defaults
and hardcoded values that fail quietly rather than dangerously.

Nothing in this repo handles credentials, so there are no secrets to leak. The
interesting surface is different: this repo's outputs are *fed to agents and
opened in browsers*, and two places take content the operator did not write and
put it somewhere it is trusted.

| # | Where | Class | Severity |
|---|---|---|---|
| F1 | `mcp-wiki-server/server.py:35-46` | unsafe default — fixed cache path in a shared directory | **High** |
| F2 | `eval-suite/generate_viewer.R:104-107` | HTML injection — model output into a `<script>` block | **High** |
| F3 | `mcp-wiki-server/.mcp.json.example` | hardcoded absolute path | Medium |
| F4 | `eval-suite/run.sh:106-134` | unescaped interpolation into JSON | Medium |
| F5 | `.github/workflows/ci.yml` | no `permissions:` block | Medium |
| F6 | `.github/workflows/ci.yml:52` | unpinned dependency installed at job time | Low-med |
| F7 | `eval-suite/recall/check_recall.py:105` | prompt passed on argv | Low |

---

## F1 — the wiki cache is a fixed path in the system temp dir, and existence is the only check

`mcp-wiki-server/server.py:33-52`:

```python
if url := os.getenv("WIKI_GIT_URL"):
    branch = os.getenv("WIKI_GIT_BRANCH", "main")
    cache = Path(os.getenv("WIKI_CACHE_DIR", tempfile.gettempdir())) / "mcp-wiki-cache"
    if cache.exists():
        refresh = subprocess.run(["git", "-C", str(cache), "pull", "--ff-only", "--quiet"], ...)
        if refresh.returncode != 0:
            print(f"[wiki] refresh failed, serving cached copy: {detail}", file=sys.stderr)
    else:
        subprocess.run(["git", "clone", "--depth", "1", "-b", branch, "--", url, str(cache)], check=True)
    return cache
```

Three properties combine badly:

1. **The path is fixed and does not depend on the URL.** With
   `WIKI_CACHE_DIR` unset it is `tempfile.gettempdir() / "mcp-wiki-cache"` —
   on Linux, `/tmp/mcp-wiki-cache`. Predictable to anyone on the host.
2. **`cache.exists()` is the entire gate.** Not "is it a git repo", not "is its
   `origin` the URL I was asked for", not "do I own it".
3. **A failed refresh is a warning, not a stop.** The `else` branch of the
   refresh explicitly commits to serving whatever is there.

So a directory planted at that path is served as the wiki, and the operator's
`WIKI_GIT_URL` is never consulted at all. Reproduced — a plain directory (not
even a git repository) at `$WIKI_CACHE_DIR/mcp-wiki-cache`, with
`WIKI_GIT_URL` pointing at a repository that does not exist:

```
[wiki] refresh failed, serving cached copy: fatal: not a git repository (or any
of the parent directories): .git
resolved root: .../faketmp/mcp-wiki-cache
served: # sql pages

- `joins.md` — # planted
```

The clone was never attempted. The nonexistent URL raised nothing. The planted
page is now tool output going straight into an agent's context — which is the
part that matters: this is not "an attacker reads your wiki", it is "an
attacker writes your agent's reference material", on a multi-user host, by
creating one directory in `/tmp`.

The same shape bites without an adversary. Point `WIKI_GIT_URL` at a second
wiki without changing `WIKI_CACHE_DIR` and the server keeps serving the first
one, silently, forever — the cache path carries no identity of what it holds.

**Suggested fix.** Two independent changes, either of which closes the
adversarial case:

- Derive the cache directory from the URL and branch — e.g.
  `f"mcp-wiki-{hashlib.sha256(f'{url}@{branch}'.encode()).hexdigest()[:16]}"` —
  which fixes the silent-stale-wiki bug too.
- Before reusing a cache, verify it: `git -C <cache> rev-parse --git-dir`
  succeeds **and** `git -C <cache> remote get-url origin` equals `url`.
  Otherwise re-clone into a fresh directory rather than trusting it.

Defaulting `WIKI_CACHE_DIR` to a private location (`platformdirs`-style user
cache, or `mkdtemp()` per process) instead of the shared temp root would be a
reasonable third layer.

## F2 — model-generated R code is embedded into a `<script>` block unescaped

`eval-suite/generate_viewer.R:104-107` splices the run payload into
`viewer.html.template` at a marker inside a script element:

```r
json <- jsonlite::toJSON(payload, auto_unbox = TRUE, null = "null", na = "null")
marker <- "/*__EMBEDDED_DATA__*/null"
parts <- strsplit(template, marker, fixed = TRUE)[[1]]
out_html <- paste0(parts[1], json, parts[2])
```

`payload$tasks[[i]]$results[[cfg]]$solution` is the verbatim contents of
`solution.R` — **whatever the coder CLI under test produced**. The whole point
of the harness is that this content is not written by the operator.

JSON serialization escapes `"`, `\` and control characters (RFC 8259).
It does not escape `<` or `/`, so the literal byte sequence `</script>` passes
through intact and terminates the HTML script element early. Reproduced by
splicing a payload whose solution contains
`cat('</script><img src=x onerror=alert(1)>')` into the real
`viewer.html.template` and asking where the browser sees the element close:

```
first </script> after <script> is at offset 3484 — i.e. inside the payload:
'</div>\n\n<script>\nconst DATA = {"tasks": [{"solution": "cat(\'</script>
<img src=x onerror=alert(1)>\')\\n"}]};\n\nfunction bad'
```

From there: `DATA` is never assigned (the statement is truncated mid-literal),
the rest of the JSON renders as page text, and the injected element runs when
the maintainer opens `runs/<ts>/viewer.html`.

*Method note:* R is not installed in this environment, so the serialization step
was reproduced with a JSON serializer implementing the same escape set rather
than with `jsonlite` itself. The claim rests on the escape set, not on the
library: `jsonlite::toJSON` has no option to escape `<`, and the repo's own
template proves the sink. Worth re-confirming with `Rscript` on a machine that
has it.

Note the template's *DOM* code is careful — it builds nodes with
`document.createElement` and assigns `textContent` (lines 77-87), never
`innerHTML`, for exactly this content. That care is defeated by the break-out,
which happens at HTML-parse time, before any of it runs.

**Suggested fix.** After serializing, escape the three sequences that can end
or start markup inside a script element:

```r
json <- gsub("<", "\\\\u003c", json, fixed = TRUE)
json <- gsub(">", "\\\\u003e", json, fixed = TRUE)
json <- gsub("&", "\\\\u0026", json, fixed = TRUE)
```

`\uXXXX` escapes are valid JSON and parse back to the same string, so nothing
downstream changes. This is the standard fix for JSON-in-`<script>`.

## F3 — `.mcp.json.example` hardcodes someone's home directory

`mcp-wiki-server/.mcp.json.example` names an absolute path twice:

```json
"args": ["run", "--directory", "/home/user/agents/mcp-wiki-server", "python", "server.py"],
"env": { "WIKI_PATH": "/home/user/agents/mcp-wiki-server/wiki" }
```

The README instructs: *"Copy `.mcp.json.example` into your project as
`.mcp.json` (or merge it into `~/.claude.json` for global use)"*. Followed
literally, that yields a config pointing at a directory that does not exist on
the reader's machine — and the failure surfaces as an MCP server that will not
start, not as "you forgot to edit a path". It also publishes the author's
directory layout, which is the smaller half of the problem.

Handed to this job by the `deps-audit` run of 2026-08-25 (see that report's
"Handed to other jobs"). The same-day `doc-drift` run deliberately left it
alone: the fix is the config file, not the prose describing it, so it belongs
here.

**Suggested fix.** Use an obvious placeholder — `/absolute/path/to/agents/mcp-wiki-server` —
and add one line to the README's "From Claude Code" section saying both paths
must be edited. A placeholder that cannot possibly work is safer than a path
that works on exactly one machine.

## F4 — `meta.json` is assembled by string interpolation

`eval-suite/run.sh` builds a JSON document with shell string concatenation.
Two fields take values the script did not construct:

```bash
raw_model=$(jq -r '.model // .small_model // empty' "$oc_config")
[[ -n "$raw_model" ]] && model_json="\"$raw_model\""
...
flags_json="[$(echo "$opencode_flags" | tr ' \n' '\0' | xargs -0 printf '"%s",' | sed 's/,$//')]"
```

`$raw_model` comes from the user's `~/.config/opencode/opencode.json`;
`$opencode_flags` from `configs/<name>/flags`. A `"` or `\` in either lands
unescaped inside a JSON string literal, producing a `meta.json` that
`read_json_safe()` in `generate_viewer.R` silently turns into `NULL`
(`tryCatch(..., error = function(e) NULL)`) — so the run's model, flags and
timings vanish from the viewer with no error anywhere.

Not remote input, so this is a robustness footgun rather than an attack, but
it is the same class as F2: unvalidated content interpolated into a structured
format instead of being encoded for it.

**Suggested fix.** The script already requires `jq` for reading this file.
Build the document with `jq -n --arg model "$raw_model" --argjson flags
"$flags_json" '{model: $model, ...}'` and let `jq` do the encoding.

## F5 — CI grants the workflow default token permissions

`.github/workflows/ci.yml` has no `permissions:` block, at either workflow or
job level, and triggers on `on: push` and `on: pull_request`. The job therefore
runs with whatever the repository default is — which for repositories created
before GitHub's default change is `write` across every scope.

The `checks` job needs nothing but a checkout: it lints, runs generators in
`--check` mode, and runs unit tests. It does `pip install` from PyPI, so a
compromised package would execute inside a job holding whatever that token can
do.

**Suggested fix.** Add at the top of the workflow:

```yaml
permissions:
  contents: read
```

One key, no behavioural change for this job, and it caps the blast radius of
every third-party action and package the workflow pulls.

## F6 — `pyyaml>=6` is installed unpinned, in a workflow that pins on principle

`.github/workflows/ci.yml:52` runs `pip install "pyyaml>=6"` inside the "Skill
frontmatter valid" step. Eleven lines above it, `ruff==0.15.8` carries a
comment explaining exactly why pinning matters here:

> *Pinned: ruff 0.16.0 shipped stricter defaults (…) that flag pre-existing
> first-party files unrelated to any given PR. Bump deliberately alongside a
> lint-cleanup pass, not implicitly per run.*

The reasoning applies as much to pyyaml: an unpinned floor resolves to whatever
PyPI serves at job time, so a bad release turns a green PR red for reasons
unrelated to its diff, and a malicious one executes in CI. The two GitHub
Actions (`actions/checkout@v4`, `actions/setup-python@v5`) are pinned only to
major tags, which the `deps-audit` run already flagged as F4.

**Suggested fix.** `pip install "pyyaml==6.0.3"` (or whatever the current
release is), with the same one-line rationale comment. Best folded into the
CI-bump PR the `deps-audit` report already proposes for F3/F4 rather than done
on its own.

## F7 — the recall check passes its prompt on the command line

`eval-suite/recall/check_recall.py:104-109`:

```python
result = subprocess.run(
    ["claude", "-p", instruction, "--model", model],
    capture_output=True, text=True, timeout=120,
)
```

`instruction` is the full menu plus the user request, so it is visible in `ps`
output to every user on the host for the duration of the call, and lands in
shell history if the equivalent is ever run by hand.

The repo has already decided against this elsewhere:
`skills/skill-creator/scripts/utils.py:coder_cli_invoke` feeds the prompt on
stdin, and its docstring says so — *"The prompt is fed on stdin so it can embed
arbitrarily large content (e.g. a whole SKILL.md body) without hitting argv
limits."* The argv limit is the stated reason; not being world-readable is the
free second one.

Low severity here because the content is skill descriptions from a public
repository. Worth aligning anyway, since the better pattern is already written
two directories away.

**Suggested fix.** `["claude", "-p", "--model", model]` with
`input=instruction`, matching `coder_cli_invoke`.

---

## Checked and found sound

Recorded so a later run does not re-litigate them.

- **Path traversal in the wiki server** — `render()` resolves
  `(base / page).resolve()` and rejects anything failing
  `is_relative_to(topic.resolve())`, comparing against the topic's *real* path
  so a symlinked topic directory does not widen it. Verified against a
  `topic/linked -> ../../outside` symlink: `page=linked/private.md` returns
  `Page not found`, and on CPython 3.11 `rglob` does not descend into the
  symlink either, so the table-of-contents and query paths do not leak it.
- **Option injection into `git clone`** — the argv is
  `["git", "clone", "--depth", "1", "-b", branch, "--", url, str(cache)]`. The
  `--` guard stops a URL beginning with `-` from parsing as an option, and
  `branch` is consumed positionally by `-b`. No shell is involved anywhere in
  `server.py`; every `subprocess.run` takes a list.
- **TOML injection via `install.sh`'s codex overrides** —
  `render_skill_override_toml` rejects any name not matching
  `^[A-Za-z0-9_-]+$` and warns, so a skill directory named
  `x"]\nenabled = true\n[[x` cannot forge a table.
- **`install.sh` never overwrites what it did not create** — every generated
  agent file carries `AGENT_MARKER` and is skipped if a file at that path lacks
  it; `unlink_one` removes a symlink only when its target is inside this repo;
  the managed config blocks are left entirely alone when their markers are
  unbalanced. `write_codex_config` writes temp-then-`mv`, so an interrupt cannot
  leave a half-written `~/.codex/config.toml`.
- **No secrets in the tree** — a case-insensitive sweep for
  `api[_-]?key|secret|token|password|credential` assignments returns only
  eval-suite *task fixtures* (`ApiKey: xxxxxxxx` in a `curl` prompt,
  `api_key = api_key` in an R snippet, `refresh_token` in a partial-matching
  example). All are illustrative inputs for R coding challenges; none is a
  value.
- **`skills/skill-creator/scripts/utils.py:coder_cli_invoke`** — backend
  selected from a fixed dict keyed by `$CODER_CLI`, rejected with a list of
  supported values if unknown; `shutil.which` checked before launch; argv is a
  list, never a shell string.

## Prompt-injection surface (noted, not a defect)

Both the wiki server and the eval harness move text from disk into a model's
context: `wiki_<topic>` tool output, and `judge.R` embedding each `solution.R`
into the judge prompt. Neither marks that content as untrusted. That is normal
for tools of this shape and not a bug to fix here, but it is the reason F1
matters more than "someone can plant files in `/tmp`" usually does — the planted
file is *instructions the model reads*.

## What this run did not do

Report-only by catalogue rule; no code changed. F1 and F2 are the two worth a
follow-up PR, and they are independent — different files, different reviewers'
attention. F5 and F6 are one-line CI edits that fold naturally into the
CI-bump PR the `deps-audit` report already proposes.
