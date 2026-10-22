---
name: poc-spec-loop
category: workflow
activation: command
disable-model-invocation: true
environments: coding
compatibility: Requires jq, one loop runner CLI (claude, codex, or opencode), and the forge CLI (gh, or az with the azure-devops extension) on PATH, a single GitHub or Azure DevOps Services remote, plus the language toolchain in references/toolchains.md (uv, R/Rscript, or bats/shellcheck/shfmt).
description: Takes a greenfield R, Python, or bash PoC to production readiness in two gated phases — interactive spec, then a per-task TDD loop with fresh context up to a pull request. Use when productionizing a greenfield PoC.
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

Not for existing codebases, not for a single bugfix or TDD without the loop (use the `tdd` skill instead), not for throwaway prototypes exploring a design question (use the `prototype` skill instead), and not for pure code reviews (use the `code-review` skill instead).

## Preconditions — verify, then stop on the first failure

Common to both phases:

1. `git remote -v` shows exactly one remote, on a supported **forge**: `github.com` (GitHub) or `dev.azure.com` / `*.visualstudio.com` (Azure DevOps Services). Azure DevOps Server and other hosts are out of scope. Repo creation is a human step, out of scope.
2. Working tree clean.
3. Language toolchain for the detected/asked language is installed per [references/toolchains.md](references/toolchains.md) `## Detect`. Missing tool → stop with the install line from that file.

Phase 1 only:

4. `main` exists and has no commits beyond an initial README/LICENSE/.gitignore. Otherwise: stop, name the missing condition. (In Phase 2, `main` legitimately carries the Phase 1 spec commit, so this check does not apply there.)

Phase 2 only:

5. `plans/prd.json` has `approved: true` (see Dispatch).
6. The **loop runner** is chosen: `claude`, `codex`, or `opencode` — the agent CLI that runs each task headlessly. Default to the runtime you are running in; ask only if that is none of the three. Its CLI, `gh`, `jq`, and GNU `timeout` are on `PATH`, and its non-interactive permission flags match the installed version (see `assets/loop.sh` header). Without them, headless tool calls are denied and every task fails its check.
7. The `tdd` and `code-review` skills are visible to a headless run only if they are installed for the runner's CLI on this machine. Check by asking the runner, headless, to list its available skills. If missing, the loop still runs — the task prompt spells out red-green-refactor itself, and the checkpoint falls back to a plain review against `SPEC.md` — but say so to the user before starting.

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
4. **Write `plans/SPEC.md`**: frontmatter (`language`, `target`, `created`), `## Goal`, `## Users`, `## Non-goals`, `## Assumptions` (answers quoted verbatim), `## Definition of Done` (the target's three lines from [references/deploy-targets.md](references/deploy-targets.md), the user's "done" answer, and on Azure DevOps the two human CI steps from toolchains.md `## CI`).
5. **Write `plans/prd.json`** against [assets/prd.schema.json](assets/prd.schema.json): 15–30 items with `origin: spec`, dependency-ordered. Item 1 is always toolchain scaffold (minimal layout from toolchains.md `## Scaffold`), item 2 is always CI: `ci.sh` plus the forge's CI file, per toolchains.md `## CI`, with `check: bash ci.sh`. A Dockerfile item exists only when the target's DoD requires it. Every item carries `check` as a literal shell command whose exit code is the verdict, or `check: null` with `manual_reason` set. No item may list a `check: null` item in `deps` — the loop never passes manual items, so such a dependent could never run. `approved: false`. An item whose code other items call ends its `detail` with `Produces: <exact name(params) -> type>`. Its dependents end theirs with `Consumes: <same signature>`. Before committing, check that every Consumes matches a Produces in its `deps` verbatim.
6. Commit both files on `main` as `chore(plans): spec and prd for <project>`. Stop. Completion criterion: both files committed, every prd item has a non-empty `check` or a `manual_reason`, no `deps` on manual items.

## Phase 2 — Loop (autonomous)

The skill's only action here is:

```
POC_AGENT=<runner> bash <skill-dir>/assets/loop.sh
```

`POC_AGENT` is required (`claude`, `codex`, or `opencode`); `loop.sh` exits 2 without it rather than guess. With `codex`, the runner gets full filesystem access — its `workspace-write` sandbox keeps `.git` read-only, and every task must commit — so run the loop in a container or VM.

`loop.sh` owns the loop; each task runs in a **fresh** runner context that sees only `SPEC.md`, the one prd item, and [assets/task-prompt.md](assets/task-prompt.md).

**Enforced by `loop.sh`** (mechanically, independent of model behaviour):

- Branch `poc/<YYYY-MM-DD>`, created from `main` on first run; the loop itself only commits on that branch. A restart (from `main` or the branch) resumes the newest existing `poc/*` branch.
- `deps` naming an id that does not exist abort the run before it starts.
- Run logs and the last failure output live under `.git/poc-loop/`, never in the working tree, so a stopped run restarts without cleanup.
- After the task, uncommitted changes are discarded (`git reset --hard` + `git clean -fd`, ignored files kept): only committed work counts, and nothing leaks into the next task. Then the script runs `check` literally, under `timeout` (`CHECK_TIMEOUT`, default 900 s). Exit 0 → `passes: true`. Otherwise `attempts` +1; at 3 the item goes to `plans/BLOCKED.md` with the last failure output and the loop moves on. A `BLOCKED:` line on the task's stdout blocks the item immediately.
- `check: null` items are never selected and never marked `passes: true`; they stay open for the human in the PR.
- **Checkpoint** every 5 passed items: a separate runner context runs the `code-review` skill since the branch start. Spec findings become new prd items (`origin: checkpoint`, `deps` on the causing item); standards findings go to `plans/REVIEW.md` and from there into the PR body. Checkpoint items may push the list past the Phase 1 range, up to the schema cap of 40; findings beyond the cap go to `REVIEW.md` instead of `prd.json`.
- **Stop the whole run** when 3 consecutive items land in BLOCKED, or when item 1 or 2 (toolchain, CI) blocks → **draft** PR immediately, listing the open items under `## Not reached (run stopped early)`.
- **Unreachable items**: when no item is selectable but some with a `check` are still open (their `deps` include a blocked item), the run ends with a **draft** PR that lists them under `## Unreachable`.
- **End of run**: PR `poc/<date>` → `main` with item checklist, open `manual_reason` items, BLOCKED.md contents, standards findings and the `## Definition of Done` section of `SPEC.md` as deployment instructions. Ready PR only if nothing is blocked or unreachable. `loop.sh` opens it itself; when you have to open or update that PR by hand (say, after a failed push), use the GitHub MCP tools if the session has them; otherwise `gh api repos/{owner}/{repo}/pulls` (REST), with `plans/PR.md` as the body.

**Requested in the task prompt** (model discipline, not checked by the script):

- Per task up to three commits, Conventional Commits with the prd id as scope: `test(prd-07): …` (red), `feat(prd-07): …` (green), `refactor(prd-07): …` (only if non-empty). TDD discipline itself is the `tdd` skill's — the task prompt points there, this file does not restate it.
- No placeholders, no mocks in production code; no edits to `plans/`.

Completion criterion for the skill: PR URL printed, and every item in `prd.json` is `passes: true`, listed in BLOCKED.md, carries a `manual_reason`, or is listed as unreachable in the PR body.

## Conventions

| Concern | Fixed to | Source of truth |
|---|---|---|
| Branch | `poc/<YYYY-MM-DD>` | `loop.sh` |
| Loop runner | `POC_AGENT=claude\|codex\|opencode`, required; one runner for tasks and checkpoints | `loop.sh` |
| State | `plans/SPEC.md`, `plans/prd.json`, `plans/BLOCKED.md`, `plans/REVIEW.md`, `plans/PR.md` (full PR body) — committed, CI ignores `plans/**` | this file |
| Toolchain per language | detect / scaffold / test / lint / typecheck commands | `references/toolchains.md` |
| Definition of Done per target | smoke command, required artefact, non-goal | `references/deploy-targets.md` |
| Forge | detected from `origin`: GitHub → REST pulls endpoint via `gh api` (a headless script cannot call MCP tools, and GraphQL-backed `gh pr create` fails in sessions where GitHub's GraphQL endpoint is blocked); Azure DevOps Services → `az repos pr create`, description cut to the checklist plus a pointer to `plans/PR.md` (4,000-character cap) | `loop.sh` |
| No placeholders, no mocks in production code | hard rule (prompt-level) | `assets/task-prompt.md` |

## Provenance

When each toolchain version, runner flag and `az` flag was last checked, what
has never run for real, and when the skill is retired, is in
[references/provenance.md](references/provenance.md); read it before the
first real run. `scripts/test_loop.py` is the stub-CLI test suite for
`loop.sh`; the skill never runs it.
