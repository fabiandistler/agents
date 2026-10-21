# Pruning the instruction fragments

Research date: 2026-10-21. Companion to
[`instruction-loading-alternatives.md`](instruction-loading-alternatives.md),
which decides *where* each fragment loads. This page decides, bullet by bullet,
what should still exist: **KEEP**, **CUT**, or **MOVE** (with a target). Line
numbers refer to `instructions/*.md` at commit `86eed88`.

## Contents

- [Criteria and how they were checked](#criteria-and-how-they-were-checked)
- [20-coding-standards](#20-coding-standards)
- [25-module-design](#25-module-design)
- [30-python](#30-python)
- [40-r](#40-r)
- [50-dev-practices](#50-dev-practices)
- [55-bug-fixing](#55-bug-fixing)
- [60-code-comments](#60-code-comments)
- [70-code-review-conventions](#70-code-review-conventions)
- [80-agent-pipelines](#80-agent-pipelines)
- [85-agent-scripts](#85-agent-scripts)
- [Cross-cutting findings](#cross-cutting-findings)
- [Tokens after pruning](#tokens-after-pruning)
- [Sources](#sources)

## Criteria and how they were checked

- **Duplicated**: grep over `skills/`, `.claude/skills/`, `AGENTS.md`, `docs/`.
  The generated copies in `.claude/rules/agents-*.md` are renders of the same
  source (`scripts/build_project_claude.py`), so they do not count as duplicates.
- **Tooling**: the fragments are *global*, so a linter only counts when it is
  on by default in the tool the fragment itself prescribes. I ran
  `ruff 0.16.10 check --isolated --show-settings` to get the real default set
  (413 rules).
- **Model default**: only claimed where the harness's own system prompt says
  it. Claude Code: the Piebald-AI extraction for v2.1.306 [cc-prompts]. Codex:
  `codex-rs/core/gpt_5_1_prompt.md` and `gpt_5_codex_prompt.md` on `main`
  [codex-prompt]. opencode was not checked; a rule that only Claude's prompt
  covers stays, because the block also goes to Codex and opencode.
- **Stale facts**: checked on the web (see [Sources](#sources)).
- The `[rule]` prefix in 20, 30, 40 and 50 is treated as noise throughout. It
  carries no meaning the bullet does not already carry, and 25, 55, 70, 80 and
  85 do without it. Dropping it saves ~2 tokens per bullet.

## 20-coding-standards

- L8 English text → **KEEP** → not covered by either system prompt. It is a
  personal override: the user's own skills write German (`skills/was`).
- L9 search for an existing helper before writing one → **KEEP, and absorb
  70 L8** → 70 L8 is the same rule seen from the reviewer's side. One bullet
  can name both moments: "before writing a helper, or accepting one in review".
- L10 broad exceptions / return a default → **KEEP** → Python half is partly
  tooling-enforced: `BLE001` blind-except, `S110` try-except-pass and `S112`
  try-except-continue are in ruff 0.16's default set (verified locally). The
  "return a default" half and R's `tryCatch` are not. Claude's prompt covers
  something nearby ("Don't add error handling, fallbacks … for scenarios that
  can't happen", `doing-tasks-no-unnecessary-error-handling`). Codex's does not.
- L11 no record values in logs → **KEEP** → closest is
  `skills/llm-application-engineering/references/agent-engineering-conventions.md:173`
  (PII in observability), but that only loads for agent work. No linter checks it.
- L12 raise or log, never both → **KEEP** → no default ruff rule (`TRY401`
  verbose-log-message is a different check), and neither prompt covers it.
- L13 dependency order (stdlib, platform, installed) → **KEEP, merge with
  L14** → both cover "adding a dependency". One bullet saves ~30 tokens.
- L14 confirm the package in the index → **KEEP (merged)** → counters
  slopsquatting. Nothing else in the repo says it.
- L15 domain names, not `data`/`result` → **KEEP (vague)** → partly overlaps
  the "Mysterious Name" smell in `.claude/skills/code-review/SKILL.md:45`, which
  only loads for reviews and only in this repo. It is a judgement call, but it
  goes against a real model habit.
- L16 no option until a caller passes it → **KEEP** → Claude's prompt covers it
  ("Don't design for hypothetical future requirements",
  `doing-tasks-no-unnecessary-additions`, ccVersion 2.1.161), and so does
  "Speculative Generality" in `.claude/skills/code-review/SKILL.md:53`. Codex's
  only says "minimal and focused" (`gpt_5_1_prompt.md:153`). It is one line, so
  keeping it for Codex and opencode is cheap.
- L17 untrusted input never as template source → **KEEP, shorten the
  rationale** → the CVE is real and the description fits: GitLab AI Gateway
  CVE-2026-90970, disclosed 2026-10-02, CVSS 9.9, "escape the prompt template
  sandbox … arbitrary command execution" [gitlab-cve]. The advisory does not
  name the engine or say that user text became template source, so "was a
  prompt-template sandbox escape" is accurate but "untrusted text as template
  source" is the fragment's own inference. Cut the parenthetical down to
  "(CVE-2026-90970)" to save ~15 tokens.

## 25-module-design

- L8 "Cut modules by shared knowledge" → **KEEP** → this is the same premise
  as `skills/coupling-cohesion/references/balanced-coupling-model.md:23`, but
  that file only loads with the skill.
- L10 phase-named files: check for duplicated format knowledge → **KEEP** →
  goes against a model habit (models default to load/clean/save splits), and no
  other file says it.
- L11 a pass-through wrapper is not a layer → **KEEP, merge with L12** → the
  same idea appears in `skills/coupling-cohesion/references/remediation.md:50`
  ("Collapse pass-through layers"), `skills/improve-codebase/references/design-vocabulary.md:100`
  and the "Middle Man" smell (`.claude/skills/code-review/SKILL.md:55`). All of
  those load on demand only.
- L12 a new layer only with its own abstraction → **MERGE into L11** →
  restates L11 from the other side. **Vague**: "never for technical reasons"
  does not say what counts as a technical reason.
- L13 dependencies point from specific to general → **KEEP** → this is the
  Stable Dependencies Principle (`skills/coupling-cohesion/references/metrics.md:103`),
  which only loads for metric work.

## 30-python

- L8 use uv → **KEEP** → a preference no prompt states.
- L9 use ruff → **KEEP** → same.
- L10–28 new-project baseline (command + TOML) → **MOVE** to a pointer file
  that loads on `uv init` (the Tier B hook in the loading research) → it is
  ~70% of the fragment and applies once per project. It is already duplicated
  almost verbatim in `skills/poc-spec-loop/references/toolchains.md:19-38`, and
  the two have started to drift: toolchains says "uv 0.12" and leaves out the
  `pip-audit` rationale and the `--exclude-newer-package` escape hatch.
- L30–36 "Why" list → **MOVE with the baseline** (the fragment says to keep
  it, and it is the part that stops edits being undone). Fact check:
  - L31 "since ruff 0.16 the default set (413 rules) already covers `UP`,
    `DTZ` and `B`" → **current**. 413 rules, with 42 UP, 10 DTZ and 29 B,
    verified on 0.16.10 [ruff-016] [ruff-local].
  - L32 "The default has only 3 of them [S rules]" → **current**: S102, S110,
    S112.
  - L35 "Relative durations need uv ≥ 0.9.17" → **current** [cooldowns]
    [owasp-cooldown]. But the escape hatch on the same line,
    `--exclude-newer-package "<package>=false"`, needs uv ≥ 0.9.25
    [pydantic-ai-pyproject], so the stated floor is too low for the advice that
    follows it. Fix: "≥ 0.9.17 (≥ 0.9.25 for the per-package `false`)". The
    "check `uv --version` first" step is now near-dead weight: the session's
    uv is 0.11.32. Keep it as a parenthetical, not an instruction.
  - L36 "`ty` … still beta" → **current** [ty-beta]. The prek pin is
    `v0.0.84`. "Same checker the prek hooks run" is **setup-specific**: it
    refers to the `prek-hooks` skill in the external repo-maintenance plugin
    (named in `toolchains.md:52`), not to anything the global reader can see.
    Reword it to "the type checker" or name the source.

## 40-r

Already path-scoped for Claude. The cuts matter for Codex and opencode, where it
is always on (~580 tokens).

- L9 `message()`/`warning()`, not `print()`/`cat()` → **KEEP, merge with L10**
  → the two bullets cover one rule and its exception.
- L10 `cat()` only in `print()` methods → **MERGE into L9**.
- L11 `{data.table}` over `{dplyr}` → **KEEP** → a preference that runs
  against the model default.
- L12 tidyverse style guide and design principles → **CUT the style half,
  flag the rest** → lintr's defaults "are intended to conform to the tidyverse
  style guide" [lintr], and `air` (in `skills/poc-spec-loop/references/toolchains.md:61`)
  formats to it. **Vague and in tension with L11**: "tidyverse design
  principles" next to "data.table, not dplyr" gives no testable rule. If the
  point is the API-design principles, L16–22 already make them concrete.
- L13 no `set.seed()`, use `withr::local_seed()` → **KEEP, scope it** →
  **vague**: as written it bans `set.seed()` in analysis scripts too. It
  presumably means package and test code.
- L14 namespace rules → **KEEP** → package-specific and not in any skill.
- L15 state and persistence → **KEEP** → the CRAN home-directory rule is
  current CRAN policy.
- L16–22 API design of exported functions → **KEEP** (path-scoped) → in no
  skill. Alternatively, move it to a reference file when `paths:` cannot
  apply (Codex, opencode).
- L23–29 domain model in R6 → **MOVE** to `skills/ddd/references/` as an R
  implementation page → half of it duplicates
  `skills/ddd/references/implementation-conventions.md`: L28 "by ID only" =
  ddd:23, L24 "access only through methods" ≈ ddd:28, L27 "no ID" = ddd:40.
  The CRUD exception at L23 is the ddd SKILL.md:39 Transaction Script branch.
  What is R-specific (R6, `private$validateInvariants()`, `checkmate`) belongs
  next to it. L29 "one package equals one bounded context" also needs checking
  against ddd:50 ("Size a bounded context as a function of its model").

## 50-dev-practices

- L8 always connect issues with PRs → **KEEP, reword** → **vague**: it does not
  say what to do when no issue exists, or how to link one. Concrete version:
  "a PR body names its issue (`Closes #n`); with no issue, say so". This is
  already the pattern in `skills/release-pr/SKILL.md:212`.
- L9 single-purpose diff → **CUT** → both system prompts cover it. Codex:
  "Changes should be minimal and focused on the task" (`gpt_5_1_prompt.md:153`).
  Claude: "A bug fix doesn't need surrounding cleanup"
  (`doing-tasks-no-unnecessary-additions`).
- L10 refactoring in its own commit → **KEEP** → in no prompt. The
  `refactoring` skill only states it when that skill is invoked.
- L11 tests with the change → **KEEP** → it overrides a stated default: Codex's
  prompt says "do not add tests to codebases with no tests"
  (`gpt_5_1_prompt.md:166`).

## 55-bug-fixing

- L8 grep all callers and fix the shared function → **KEEP** → Codex has only
  the generic "Fix the problem at the root cause … when possible"
  (`gpt_5_1_prompt.md:149`), and Claude has nothing. `diagnosing-bugs` talks
  about callers for repro shrinking only (`.claude/skills/diagnosing-bugs/SKILL.md:80`).
- L9 stop after the third failed fix → **KEEP** → no prompt or skill sets a
  count.

## 60-code-comments

- L8 do not remove existing comments → **KEEP** → it counterweights Claude's
  "Default to writing no comments … If removing the comment wouldn't confuse
  a future reader, don't write it" (`comment-why-only-guidance`), which pushes
  toward fewer comments. Codex's "Do not add inline comments" (`gpt_5_1_prompt.md:158`)
  says nothing about removing them. Note: `scripts/build_project_claude.py:56`
  skips this fragment for this repo on purpose.

## 70-code-review-conventions

Whole fragment: **MOVE** to an on-demand file, per the loading research. In
this repo, `.claude/skills/code-review/SKILL.md` step 3 already collects
`.claude/rules/*` as a standards source.

- L8 grep the repo for a duplicate helper → **CUT here, merge into 20 L9** →
  same rule (see above).
- L9 review in order of cost to change → **KEEP** → overrides Codex's review
  default, "ordered by severity" (`gpt_5_codex_prompt.md:31`). The reason to
  keep it is that it contradicts a prompt default.
- L10 API surface is wider than exports → **KEEP** → in no skill or prompt.
- L11 new API as small as possible → **TRIM to "not tailored to a single
  caller"** → **vague**: "as small as possible, one way to do one thing" is
  generic, and it overlaps 20 L16 and Claude's no-unnecessary-additions prompt.
- L12 no formatting/naming comments; report a missing CI gate → **KEEP the
  CI-gate half** → "skip anything tooling enforces" is already in
  `.claude/skills/code-review/SKILL.md:41,66` (repo-local, vendored) and in
  80 L12. The "report it once as a missing CI gate" twist appears nowhere else.

## 80-agent-pipelines

Whole fragment: **MOVE** to `skills/llm-application-engineering/references/`
(an `agent-pipeline-conventions.md` page, or a section of
`agent-engineering-conventions.md`), per the loading research. That page
carries a keep-filter (`agent-engineering-conventions.md:14-15`: "Generic best
practice a competent model already follows is omitted"); the verdicts below
apply it.

- L8 finder does not grade → **KEEP**.
- L9 anchored 0/25/50/75/100 scale → **KEEP, but reconcile first** →
  **contradicts** `ai-engineering-conventions.md:74-77`: "binary pass/fail judge,
  never a continuous score … Use a discrete scale only with an explicit
  reason", which lists `"rate from 0 to 100"` as the likely-default
  anti-pattern. A five-level anchored scale is discrete, but the fragment gives
  no reason for it. Add one (for example, ranking findings against a threshold
  needs more than pass/fail) or the two pages disagree once they sit next to
  each other.
- L10 the threshold applies before writing → **KEEP**.
- L11 silence is a valid output → **KEEP** → contradicts Codex's interactive
  default ("If no findings are discovered, state that explicitly",
  `gpt_5_codex_prompt.md:31`), so it has to be said. Scope it to unattended
  pipelines.
- L12 false-positive catalogue in the finder → **KEEP** → the list overlaps
  70 L12. Fine, since they load at different times.
- L13 split finders by evidence source → **KEEP**.
- L14 cheap model for classification and grading → **CUT on move** → already
  `ai-engineering-conventions.md:35-36` ("route the simple steps to cheaper
  models (e.g. intent classification)") and :90-91 ("Layer evaluators by
  cost"). It also sits uneasily with :84-86, which requires calibrating each
  judge against ~100 human-labelled traces. A cheap grader needs that check
  first.
- L15 strip untrusted text → **KEEP** → the general point (treat it as
  untrusted) is `agent-engineering-conventions.md:171` and
  `ai-engineering-conventions.md:46`. The concrete strip list and "the output
  is a recommendation" are new.
- L17 re-check right before the write → **KEEP, merge L17–L19 into one
  bullet** → three bullets for one mechanism: re-check, why a state file is
  also needed, abort without side effect.
- L18 state file plus re-check → **MERGE into L17**.
- L19 abort with one log line → **MERGE into L17**.
- L20 no write credential for an unattended LLM step → **KEEP** → stricter
  than `ai-engineering-conventions.md` "Gate all mutating actions … behind
  explicit human approval" (:242). It is the model-free publish step that
  makes it new.
- L21 path allowlist including untracked files → **KEEP**.
- L22 self-edits through the same allowlist; loosening is reported → **KEEP**.

## 85-agent-scripts

Whole fragment: **duplicated on purpose** in `AGENTS.md:244-275`. AGENTS.md
says "edit both when they change", and the global copy is needed outside this
repo. Per the loading research, **MOVE** it to an on-demand file. In this repo
AGENTS.md keeps carrying it for Codex and opencode, and Claude gets it from
`.claude/rules/agents-85-agent-scripts.md`.

- L10 never read from an interactive prompt → **KEEP** → neither prompt tells
  the model how to *write* scripts. Claude's Bash tool text covers only *running*
  interactive flags.
- L11 `--help` as the only interface doc, ≤25 lines → **KEEP**.
- L12 distinct exit codes, data to stdout → **KEEP**.
- L13 one named verb per write, `--dry-run` first → **KEEP**.
- L14 secrets from env, never a flag → **KEEP**.
- L15 smoke-test the installed command from `/tmp` → **KEEP**.
- L16 bound the output, "truncated past roughly 10–30k characters" →
  **KEEP** → Claude's Bash tool caps output at 30,000 characters by default
  [cc-bash-limit]. The Codex figure was not re-verified, so the "10k" low end
  is unconfirmed.

## Cross-cutting findings

- **Contradiction to fix before any move**: 80 L9 against
  `ai-engineering-conventions.md:74-77` (grader scale).
- **Prompt defaults that the fragments override**, so they must stay explicit:
  70 L9 (cost order vs. severity order), 50 L11 (tests vs. "no tests in
  test-less repos"), 80 L11 (silence vs. "state no findings").
- **Already duplicated in skills, drifting**: the Python baseline
  (`toolchains.md`) and half of the R6 block (`ddd`). Moving gives each fact
  one owner. Since skills must stay self-contained, `toolchains.md` keeps its
  copy, so a drift check would be needed if both remain.
- **Nothing is purely this-repo-only** apart from 30 L36 ("the prek hooks")
  and 85, which AGENTS.md already mirrors on purpose.
- **Vague or unenforceable**: 25 L12, 40 L12, 40 L13, 50 L8, 70 L11, plus the
  `[rule]` prefix.

## Tokens after pruning

Body bytes / 4, as in the loading research. "Always-on" assumes that page's
Tier A/B/C split is applied too (70, 80, 85 and the Python baseline become
on-demand files, with a ~20-token pointer each).

| Fragment | Now (~tokens) | After pruning, always-on (~tokens) |
|---|---|---|
| 20-coding-standards | 433 | ~350 |
| 25-module-design | 163 | ~130 |
| 30-python | 493 | ~60 (+ ~420 on-demand baseline) |
| 40-r | 579 | ~400 (path-scoped in Claude; R6 ~150 moved to ddd) |
| 50-dev-practices | 52 | ~40 |
| 55-bug-fixing | 95 | 95 |
| 60-code-comments | 30 | 30 |
| 70-code-review-conventions | 217 | ~20 pointer (+ ~150 on-demand) |
| 80-agent-pipelines | 561 | ~20 pointer (+ ~420 on-demand) |
| 85-agent-scripts | 281 | ~20 pointer (+ ~280 on-demand) |

Totals: ~2.9k now. After pruning alone, without moving anything, ~2.45k.
With pruning and the tier split: Claude ~0.7k always-on (40 and the Python
rule load on matching paths); Codex and opencode ~1.1k with 40 in the block,
or ~0.75k with 40 as a pointer too. That beats the loading research's ~0.9k
estimate by ~0.2k. Most of the gain comes from the merges in 20, 25 and 80 and
from moving the R6 block.

## Sources

- [cc-prompts] Piebald-AI, *claude-code-system-prompts*, extracted from Claude
  Code v2.1.306 (2026-10-20): `system-prompts/system-prompt-doing-tasks-no-unnecessary-additions.md`,
  `…-no-unnecessary-error-handling.md`, `…-comment-why-only-guidance.md`,
  `…-comment-what-and-task-context-avoidance.md`.
  https://github.com/Piebald-AI/claude-code-system-prompts
- [codex-prompt] openai/codex `main`: `codex-rs/core/gpt_5_1_prompt.md`
  (L149, L153, L158, L166), `codex-rs/core/gpt_5_codex_prompt.md` (L31).
  https://github.com/openai/codex
- [gitlab-cve] GitLab AI Gateway Critical Patch Release 19.2.4/19.3.2/19.4.1.
  https://docs.gitlab.com/releases/patches/other-patches/patch-release-gitlab-ai-gateway-19-4-1-released/
- [ruff-016] Astral, "Ruff v0.16.0": "Ruff now enables 413 rules by default, up
  from 59". https://astral.sh/blog/ruff-v0.16.0
- [ruff-local] `uvx ruff@0.16.10 check --isolated --show-settings`, run
  2026-10-21: 413 enabled rules, including B (29), UP (42), DTZ (10), S (3:
  S102, S110, S112), BLE001, TRY (5).
- [cooldowns] https://cooldowns.dev/ ("added support for relative durations …
  in version 0.9.17")
- [owasp-cooldown] OWASP DevSecOps Guideline, Dependency Management and
  Cooldown Policies ("uv >= 0.9.17 for relative durations").
- [pydantic-ai-pyproject] pydantic/pydantic-ai `pyproject.toml`:
  "`exclude-newer-package` `false` needs >= 0.9.25". Secondary source, not
  checked against the uv changelog.
- [ty-beta] https://github.com/astral-sh/ty ("ty is currently in beta").
- [lintr] https://lintr.r-lib.org/articles/lintr.html ("The default settings
  of lintr are intended to conform to the tidyverse style guide").
- [cc-bash-limit] anthropics/claude-code#19901 ("By default, the Bash tool
  captures a maximum of 30,000 characters").
