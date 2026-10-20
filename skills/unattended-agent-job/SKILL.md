---
name: unattended-agent-job
category: ai-ml
environments: coding
description: "Design or audit a scheduled or CI agent job so the LLM step only emits a patch or outputs file and a model-free step validates and publishes it. Covers credential split, output contract, allowlist gate, idempotency, pre-flight."
metadata:
  version: "1.0"
---

# Unattended agent job

The rules for agents that write into external systems already exist as the
*Agent pipelines* instruction fragment (`instructions/80-agent-pipelines.md` in
this catalogue, installed into the agent's global instruction file), section
*Writing into external systems*. This skill is the procedure that applies
them to one concrete job and the tooling that enforces them outside the
prompt. Read that fragment first; this file does not restate it.

## When to use

- A job runs an LLM without anyone watching — cron, a scheduled cloud
  session, a CI workflow, an API or webhook trigger — and the job writes
  somewhere: a push, a PR, an issue, a comment, a label, a database row, a
  message.
- Designing such a job, reviewing an existing one ("is it safe to let the bot
  push?"), or moving one off a write token.
- Not for: an interactive agent picking the wrong tool, prompt quality, or
  evals — read `members/llm-application-engineering/SKILL.md` via the `ai-ml`
  router. A cron job with no LLM step needs none of this.

## The shape

```
trigger → pre-flight → LLM step (read-only) → outputs/ → validator → publisher (write credential, re-check) → write
```

The LLM step reads and thinks; it holds no write credential and ends by
writing `outputs/outputs.json` (plus `outputs/patch.diff`). The **publisher**
is model-free code: it validates the outputs, re-checks the entry condition,
and performs the writes. Everything below fills in that line for one job.

## Procedure

Work on the job's real definition — workflow YAML, scheduled-task prompt,
runbook — not a description of it. Each step ends on its stated output.

### 1. Inventory every write

List every external write the job can perform, from the definition and from
the tools it is handed (an MCP connector with write tools counts even when
the prompt never mentions it). One row per write:

| Write | Target | Performed by | Credential and scope | Verdict |
|---|---|---|---|---|
| open PR | this repo | LLM session | user's GitHub identity, push to any `claude/*` | LLM holds credential |
| upload artifact | Actions run | runner, no model | `GITHUB_TOKEN`, `contents: read` | model-free |

Verdict is either *model-free publisher* or *LLM holds credential*. Done when
every write the credentials allow appears, not only those the prompt asks
for.

### 2. Place the job on the ladder

| Rung | Shape | What the next rung buys |
|---|---|---|
| 0 | LLM writes directly to the target (default branch, issue, DB) | — |
| 1 | LLM writes only to a staging branch; a human merges | writes are reversible and reviewed |
| 2 | LLM emits `outputs/`; a model-free publisher performs the writes | the credential leaves the LLM step |
| 3 | rung 2 plus the validator gate (schema, allowlist, line budget, protected paths) | scope is enforced outside the prompt |

The fragment's bar is rung 3. Name the job's current rung and the single
concrete change that lifts it one rung (for example: "split job `agent` with
`permissions: contents: read` from job `publish` with `contents: write`").
Prose limits in a prompt ("keep the diff under 200 lines", "never touch
X") leave a job on its rung; only code moves it.

### 3. Define the output contract

Copy `assets/outputs.schema.json` into the job. Delete the output kinds the
job never emits and tighten the size caps to what it needs. Targets — which
issue, which branch, which repository — stay publisher configuration; the
LLM step supplies content only. The publisher validates `outputs.json`
against the schema and refuses the whole run on a failure.

### 4. Wire the validator

The publisher, on a clean checkout of the base commit, runs:

```bash
python3 scripts/validate_patch.py --repo . --patch outputs/patch.diff \
  --allowlist <allowlist file> --max-lines <budget> \
  --protected '<job prompt>' --protected '<workflow file>'
```

It is read-only and prints one JSON report; `--help` lists the flags and exit
codes. Branch on the exit code: 0 apply and publish; 6 (protected path) open a
PR for a human instead; anything else abort with no write. Keep the allowlist
file in a protected path, so the job cannot widen its own scope. After the
gate, stage exactly the validated paths, never `git add -A`.

### 5. Decide state and the re-check

Pick where "already done?" lives:

| State source | Fits | Breaks on |
|---|---|---|
| clock-derived (ISO week, date) | fixed rotations | manual fires repeat a slot; week 53 / week 1 collide |
| state file committed by the publisher | exactly-once across runs | a run that dies after the write but before the commit |
| remote query (open PR with the job's prefix, issue label) | "skip while the last result is unreviewed" | API flavour: GraphQL-backed CLI calls may be blocked where REST works |

Then place the entry-condition re-check in the publisher, immediately before
the write, as the fragment requires. Decide explicitly what a manual fire
does: repeat the slot, or advance it.

### 6. Pre-flight

The job's first step probes what it will need and aborts with one log line
before any LLM call when a probe fails: history deep enough for the
look-back window (a shallow clone silently undercounts), the write path the
publisher will use is reachable, required CLIs exist. A failed probe means no
partial work, not a degraded run.

### 7. Fill the job sheet

Copy `references/job-sheet.md` and fill it for this job: trigger and who can
fire it, worst-case spend, timeouts, each step's credential, untrusted
inputs, runner isolation. It links the existing convention for each question
instead of repeating it.

## Platform notes

Platform specifics (GitHub Actions job split, GitHub Agentic Workflows safe
outputs, Claude Code scheduled tasks, the Codex GitHub Action) are dated and
rot fastest: read `references/platform-notes.md` when the job runs on one of
them.

## Output

Hand back, in this order: the write inventory (step 1), the job's rung and the
next change (step 2), then the concrete changes for steps 3–7 as a patch or a
checklist, and the filled job sheet. A job already on rung 3 with a complete
sheet gets that one sentence.

## Common mistakes

- Trusting the prompt to limit scope: "never edit workflows" in the prompt is
  rung 1 at best; the `--protected` gate is the enforcement.
- Inventorying only the writes the prompt asks for, while an included
  connector or token permits more.
- Letting the LLM pick the write target (issue number, branch, repository).
- Checking the entry condition only at the start of the run.
- Keeping "already done" state in the clock and forgetting manual fires.
- Reading a green run status as success: confirm what was written.
