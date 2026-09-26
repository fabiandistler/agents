---
name: poc-spec-loop
category: workflow
activation: command
disable-model-invocation: true
environments: coding
compatibility: Requires claude, gh, and jq on PATH, a single github.com remote, plus the language toolchain in references/toolchains.md (uv, R/Rscript, or bats/shellcheck/shfmt).
description: Bring a greenfield R, Python, or bash PoC to production readiness in two gated phases — interactive spec (SPEC.md + prd.json), then a per-task TDD loop with fresh context up to a pull request.
metadata:
  version: "1.0"
---

# poc-spec-loop

Two parameters, both asked at the start of Phase 1 and written into `plans/SPEC.md`:

| Parameter | Type | Written to |
|---|---|---|
| **Project goal** | free text, one paragraph | `SPEC.md` `## Goal` |
| **Deployment target** | enum: `package` · `http-service` · `mcp-server` · `cli` · `other:<text>` | `SPEC.md` frontmatter `target:` |

Everything else is detected or fixed convention — see [Conventions](#conventions). A value the skill can derive is never asked.

## When to use

Use this on explicit request to take a greenfield PoC to production readiness through the two gated phases — e.g. "poc-spec-loop", "PoC-Loop starten", "Spec-Loop für das neue Repo", or "Loop freigegeben, weiter".

Not for existing codebases, not for a single bugfix or TDD without the loop (use `mattpocock-skills:tdd` instead), not for throwaway prototypes exploring a design question (use `mattpocock-skills:prototype` instead), and not for pure code reviews (use `mattpocock-skills:code-review` instead).

## Preconditions — verify, then stop on the first failure

Common to both phases:

1. `git remote -v` shows exactly one `github.com` remote. Repo creation is a human step (`gh repo create`), out of scope.
2. Working tree clean.
3. Language toolchain for the detected/asked language is installed per [references/toolchains.md](references/toolchains.md) `## Detect`. Missing tool → stop with the install line from that file.

Phase 1 only:

4. `main` exists and has no commits beyond an initial README/LICENSE/.gitignore. Otherwise: stop, name the missing condition. (In Phase 2, `main` legitimately carries the Phase 1 spec commit, so this check does not apply there.)

Phase 2 only:

5. `plans/prd.json` has `approved: true` (see Dispatch).
6. `claude`, `gh`, `jq`, and GNU `timeout` on `PATH` and non-interactive permission flags in place (see `assets/loop.sh` header). Without the flags, headless tool calls are denied and every task fails its check.
7. `mattpocock-skills:tdd` and `mattpocock-skills:code-review` are plugin skills; a headless `claude -p` run only sees them if the plugin is installed for the CLI on this machine. Check with `claude -p "list your available skills"`. If missing, the loop still runs — the task prompt spells out red-green-refactor itself, and the checkpoint falls back to a plain review against `SPEC.md` — but say so to the user before starting.

## Dispatch — the state machine

Read `plans/prd.json` before anything else, then run the preconditions for the resulting phase.

```
plans/prd.json missing            → Phase 1
plans/prd.json  approved: false   → stop: "Set approved: true in plans/prd.json and commit to release the loop."
plans/prd.json  approved: true    → Phase 2
```

The human releases the loop by editing the flag and committing — the marker lives in the repo, never in chat.

## Phase 1 — Spec (interactive)

1. **Language.** Detect from `pyproject.toml` / `DESCRIPTION` / `*.sh`+shebang. Greenfield has nothing to detect → ask once: R, Python, or bash.
2. **Parameters.** Ask project goal and deployment target (table above).
3. **Questions.** Four mandatory, then up to four adaptive — eight total, hard cap:
   - Users and how they invoke the thing
   - Non-goals
   - Data sources, secrets, external access
   - What "done" means beyond the deployment target's smoke command
4. **Write `plans/SPEC.md`**: frontmatter (`language`, `target`, `created`), `## Goal`, `## Users`, `## Non-goals`, `## Assumptions` (answers quoted verbatim), `## Definition of Done` (the target's three lines from [references/deploy-targets.md](references/deploy-targets.md) plus the user's "done" answer).
5. **Write `plans/prd.json`** against [assets/prd.schema.json](assets/prd.schema.json): 15–30 items with `origin: spec`, dependency-ordered. Item 1 is always toolchain scaffold (minimal layout from toolchains.md `## Scaffold`), item 2 is always the GitHub Actions workflow running test + lint. A Dockerfile item exists only when the target's DoD requires it. Every item carries `check` as a literal shell command whose exit code is the verdict, or `check: null` with `manual_reason` set. No item may list a `check: null` item in `deps` — the loop never passes manual items, so such a dependent could never run. `approved: false`.
6. Commit both files on `main` as `chore(plans): spec and prd for <project>`. Stop. Completion criterion: both files committed, every prd item has a non-empty `check` or a `manual_reason`, no `deps` on manual items.

## Phase 2 — Loop (autonomous)

The skill's only action here is:

```
bash <skill-dir>/assets/loop.sh
```

`loop.sh` owns the loop; each task runs in a **fresh** `claude -p` context that sees only `SPEC.md`, the one prd item, and [assets/task-prompt.md](assets/task-prompt.md).

**Enforced by `loop.sh`** (mechanically, independent of model behaviour):

- Branch `poc/<YYYY-MM-DD>`, created from `main` on first run; the loop itself only commits on that branch. A restart (from `main` or the branch) resumes the newest existing `poc/*` branch.
- `deps` naming an id that does not exist abort the run before it starts.
- Run logs and the last failure output live under `.git/poc-loop/`, never in the working tree, so a stopped run restarts without cleanup.
- After the task, uncommitted changes are discarded (`git reset --hard` + `git clean -fd`, ignored files kept): only committed work counts, and nothing leaks into the next task. Then the script runs `check` literally, under `timeout` (`CHECK_TIMEOUT`, default 900 s). Exit 0 → `passes: true`. Otherwise `attempts` +1; at 3 the item goes to `plans/BLOCKED.md` with the last failure output and the loop moves on. A `BLOCKED:` line on the task's stdout blocks the item immediately.
- `check: null` items are never selected and never marked `passes: true`; they stay open for the human in the PR.
- **Checkpoint** every 5 passed items: a separate `claude -p` run of `mattpocock-skills:code-review` since the branch start. Spec findings become new prd items (`origin: checkpoint`, `deps` on the causing item); standards findings go to `plans/REVIEW.md` and from there into the PR body. Checkpoint items may push the list past the Phase 1 range, up to the schema cap of 40; findings beyond the cap go to `REVIEW.md` instead of `prd.json`.
- **Stop the whole run** when 3 consecutive items land in BLOCKED, or when item 1 or 2 (toolchain, CI) blocks → **draft** PR immediately, listing the open items under `## Not reached (run stopped early)`.
- **Unreachable items**: when no item is selectable but some with a `check` are still open (their `deps` include a blocked item), the run ends with a **draft** PR that lists them under `## Unreachable`.
- **End of run**: PR `poc/<date>` → `main` with item checklist, open `manual_reason` items, BLOCKED.md contents, standards findings and the `## Definition of Done` section of `SPEC.md` as deployment instructions. Ready PR only if nothing is blocked or unreachable.

**Requested in the task prompt** (model discipline, not checked by the script):

- Per task up to three commits, Conventional Commits with the prd id as scope: `test(prd-07): …` (red), `feat(prd-07): …` (green), `refactor(prd-07): …` (only if non-empty). TDD discipline itself is `mattpocock-skills:tdd`'s — the task prompt points there, this file does not restate it.
- No placeholders, no mocks in production code; no edits to `plans/`.

Completion criterion for the skill: PR URL printed, and every item in `prd.json` is `passes: true`, listed in BLOCKED.md, carries a `manual_reason`, or is listed as unreachable in the PR body.

## Conventions

| Concern | Fixed to | Source of truth |
|---|---|---|
| Branch | `poc/<YYYY-MM-DD>` | `loop.sh` |
| State | `plans/SPEC.md`, `plans/prd.json`, `plans/BLOCKED.md`, `plans/REVIEW.md` — committed, CI ignores `plans/**` | this file |
| Toolchain per language | detect / scaffold / test / lint / typecheck commands | `references/toolchains.md` |
| Definition of Done per target | smoke command, required artefact, non-goal | `references/deploy-targets.md` |
| Remote | GitHub only; PR via `gh pr create` | `loop.sh` |
| No placeholders, no mocks in production code | hard rule (prompt-level) | `assets/task-prompt.md` |

## Provenance

- Toolchain versions in `references/toolchains.md` were last verified 2026-09-07; re-verify before each real run.
- `assets/loop.sh` has not yet run against a real PoC; verify the `claude -p` flags first.
- Sunset: delete this skill on 2027-03-01 if no second real run has happened by then.
