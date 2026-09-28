# Skill audit checklist

The rubric the weekly skill audit (`docs/agents/skill-audit.md`) applies to
each selected skill. Every item has a stable ID; findings cite it, so the
audit issue can tell a new finding from one reported last week.

Only judgement calls live here. What a script already decides conclusively —
frontmatter schema, description budgets, catalogue/plugin/manifest drift,
agent-specific vocabulary, reference TOCs, eval-file shape — is CI's job
(`.github/workflows/ci.yml`); the audit runs those scripts once and never
re-reports their findings per skill.

Sources: this repo's conventions in `AGENTS.md` (*Conventions for skill
authors*, *Scripts an agent runs*) and Anthropic's *Skill authoring best
practices*
(<https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>).
When that page gains a checkable rule, add an item here in a normal PR
rather than applying it ad hoc.

## Contents

- [Severity](#severity)
- [D — Description and triggering](#d--description-and-triggering)
- [B — Body structure](#b--body-structure)
- [R — References and bundled files](#r--references-and-bundled-files)
- [S — Scripts](#s--scripts)
- [C — Content correctness](#c--content-correctness)
- [E — Evals](#e--evals)
- [X — Cross-skill consistency](#x--cross-skill-consistency)

## Severity

- **error** — the skill misleads the agent or breaks: a dead path, a wrong
  command, a factual error, a description that triggers on the wrong requests.
- **warn** — works, but against a best practice with a real cost (tokens,
  missed triggers, partial reads).
- **nit** — style. Report at most three nits per skill.

## D — Description and triggering

- **D1** Third person, states *what* the skill does and *when* to use it.
  Not "I can…", not "You can use this to…". (error if either half missing)
- **D2** Specific key terms a user would actually type; no vague verbs
  ("helps with", "handles"). (warn)
- **D3** Trigger lists and feature enumerations sit in the body's leading
  `## When to use`, not the frontmatter (AGENTS.md budget rule). (warn)
- **D4** The description matches what the body actually does — no promised
  capability the body lacks, no major workflow the description hides. (error)
- **D5** Name is specific, not generic (`helper`, `utils`, `data`), and
  follows the collection's pattern. (nit)

## B — Body structure

- **B1** Body under 500 lines; larger material moved to `references/`. (warn)
- **B2** Concise: no paragraphs explaining what a capable model already knows
  (what a PDF is, what git does). Quote the offending line. (warn)
- **B3** Multi-step workflows are numbered steps, with a validation or
  feedback loop before any irreversible or quality-critical step. (warn)
- **B4** One default per decision, with an escape hatch — not a menu of
  equivalent options. (warn)
- **B5** Consistent terminology within the skill; uses `CONTEXT.md` terms
  where the concept exists there. (nit)
- **B6** Degree of freedom fits the task: fragile sequences are exact
  commands, judgement tasks are heuristics. (warn)
- **B7** No agent-specific vocabulary the vocab script misses: proprietary
  tool names, hardcoded install paths, runtime error text. (warn)

## R — References and bundled files

- **R1** Every relative path in SKILL.md and its references exists. (error)
- **R2** References are one level deep: SKILL.md links each file it needs;
  a reference does not send the agent on to a further reference. (warn)
- **R3** SKILL.md names each reference with a one-line cue for when to open
  it; no orphan file in `references/` that nothing links. (warn)
- **R4** Files are named for their content (`form_validation_rules.md`, not
  `doc2.md`); forward slashes only. (nit)

## S — Scripts

Applies only to skills with `scripts/`.

- **S1** SKILL.md says whether to *run* or *read* each script, and the shown
  invocation matches the script's actual flags (`--help`). (error)
- **S2** Follows *Scripts an agent runs* in AGENTS.md: non-interactive,
  `--help` under ~25 lines, data to stdout, documented exit codes, bounded
  output, PEP 723 for third-party deps. (warn)
- **S3** Errors handled in the script, not deferred to the agent; no
  unexplained magic constants. (warn)
- **S4** One-off `uvx`/`npx` commands are version-pinned. (warn)

## C — Content correctness

- **C1** Commands, flags, file formats and APIs the skill prescribes still
  work as written. Verify against the tool's current docs or `--help` when
  the environment allows; otherwise mark the finding *unverified*. (error)
- **C2** No time-sensitive statements ("before August 2025…", "the latest
  version is…") outside an explicit *Old patterns* section. (warn)
- **C3** External links resolve and still say what the skill cites them
  for. Spot-check at most three per skill. (warn)
- **C4** No internal contradiction between SKILL.md and its references. (error)

## E — Evals

- **E1** `evals.json` prompts are realistic user phrasings, and the
  `should_not_trigger` prompts are near-misses that a neighbouring skill
  owns — not unrelated requests that could never trigger it. (warn)
- **E2** `expected_behavior`, when present, is checkable from a transcript.
  (nit)

## X — Cross-skill consistency

Applied once per run across all selected skills, not per skill.

- **X1** Two skills' descriptions claim the same trigger without a
  "not for … (use X)" boundary on at least one side. (warn)
- **X2** A cross-skill reference names a skill that is not registered or not
  model-invocable (AGENTS.md: command skills are suggested, router members are
  read via their router file). (error)
- **X3** The same rule is stated differently in two skills. (warn)
