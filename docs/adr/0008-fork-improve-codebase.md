# ADR-0008: Fork `improve-codebase` instead of patching the vendored command

## Status

Accepted (2026-10-13). The A/B gate passed: the runs and the verdict are in
[`docs/evals/improve-codebase-ab.md`](../evals/improve-codebase-ab.md), and the
adjustments the runs called for are in `skills/improve-codebase/`.

## Context

Matt Pocock's `improve-codebase-architecture` command finds deepening
opportunities in a codebase and then grills the user through one of them. It
gathers its evidence by hand: scope comes from eyeballing `git log`, and
exploration runs through an unspecified sub-agent. This catalogue already owns
better instruments for exactly those two steps:

- `refactoring` ranks files by git churn and lists co-changing files.
- `coupling-cohesion` measures a module's cohesion (Mode A, LCOM) and whether
  one specific dependency is balanced (Mode C), and the `architecture` plugin
  ships the `cohesion-analyst` and `coupling-analyst` subagents that run them.

The command uses neither. Spec
[#492](https://github.com/fabiandistler/agents/issues/492) wires them in. The
question this ADR answers is *where* that change lives, because the command
cannot simply be edited where it sits today:

- It is vendored into `.claude/skills/` by
  `scripts/vendor_mattpocock_skills.py`, which replaces each vendored
  directory wholesale on every re-run (pinned at upstream `49dd158`, v1.3.1).
- The vendored copy reaches Claude cloud sessions in this repo only. It is not
  part of any install surface — not `claude` via the marketplace plugin, not
  `codex`, not `opencode` (ADR-0004).
- Its text uses agent-specific vocabulary ("Call the Skill tool",
  slash-command names) that the skill-authoring conventions in `AGENTS.md`
  forbid and `scripts/check_skill_vocab.py` flags.
- It depends on three Pocock skills (`codebase-design`, `grilling`,
  `domain-modeling`) that are not part of this catalogue and are absent on
  `codex` and `opencode` unless installed separately.

## Decision

Fork the command into the catalogue as a new skill,
[`improve-codebase`](../../skills/improve-codebase/SKILL.md), in category
`refactoring`. It is a top-level command skill (`activation: command`,
`disable-model-invocation: true`, Codex sidecar with
`allow_implicit_invocation: false`), rewritten to the repo's conventions and
self-contained:

- The `codebase-design` vocabulary and principles move into a reference file of
  the skill, with MIT attribution and upstream commit `49dd158` in its header.
  The grilling loop and glossary/ADR upkeep are described in neutral prose.
- **Scope** uses the `refactoring` churn ranking and its co-change list.
- **Explore** uses `coupling-cohesion` Mode A to back up a "shallow module"
  suspicion alongside the deletion test, and Mode C for a suspected leak across
  a seam. With subagents available it delegates to `cohesion-analyst` /
  `coupling-analyst`; otherwise it runs the `coupling-cohesion` scripts inline.
- **Mode B is excluded.** Codebase-wide metrics and zones answer "how brittle
  is the whole codebase", not "where does deepening pay off", and would be
  noise in the report.
- **Pocock's vocabulary is binding** for the report and the interview (module,
  interface, depth, seam, adapter, leverage, locality). `coupling-cohesion`
  output is translated into it at the hand-off — boundary, integration
  strength and distance do not appear in the report as such.
  `coupling-cohesion` itself is not changed.
- **After the grilling loop**, a closing step points at `fitness-functions` to
  lock a chosen seam into CI.
- **No cross-references** are added from `refactoring` or `coupling-cohesion`
  to the new command.
- The vendor script gains an explicit exclusion set containing
  `improve-codebase-architecture`, so cloud sessions in this repo see one
  architecture-review command, not two near-identical ones.
- **Merge is gated on an A/B result.** One run of the original and one of the
  fork on each of `fabiandistler/escoRAG` (Python, exact LCOM) and
  `fabiandistler/lintr` (R, heuristic LCOM, long hotspot history), compared on
  whether the candidates differ, whether the top recommendation differs, and
  whether every finding carries `path:line` or metric evidence. The result is
  checked into `docs/` before merge. If the fork changes neither the outcome
  nor the evidence, it does not merge.

## Decision drivers

- **Vendor re-runs wipe in-place edits.** The vendor script owns the
  directory; any local change to the vendored command is lost on the next
  re-vendor.
- **The vendored copy reaches cloud sessions only.** A change made there never
  reaches the `claude`, `codex` or `opencode` install surfaces.
- **The original's vocabulary breaks the authoring conventions.**
  Skill-invocation phrasing and slash-command names are forbidden in skill
  bodies and caught by `check_skill_vocab.py`; the command cannot enter the
  catalogue unchanged.
- **Its Pocock-skill dependencies are missing on `codex` and `opencode`.** A
  command that defers to `codebase-design`, `grilling` and `domain-modeling`
  silently loses half its method wherever those are not installed.

## Considered options

- **Fork into the catalogue (chosen).** One self-contained skill on every
  install surface, under the repo's conventions and CI checks. Costs upstream
  drift (see Consequences).
- **Patch overlay in the vendor script.** Apply a diff to the vendored copy
  after each re-vendor. Rejected: the patch breaks whenever upstream touches
  the same lines, the result still reaches cloud sessions only, and it keeps
  the dependencies on the three Pocock skills.
- **Upstream PR to mattpocock/skills.** Rejected: the change names this
  catalogue's own skills (`refactoring`, `coupling-cohesion`, the analyst
  subagents), which do not exist upstream, and even an accepted PR would leave
  the `codex` / `opencode` and vocabulary problems unsolved here.
- **Cross-reference only.** Add pointers from `refactoring` and
  `coupling-cohesion` to the vendored command, or the other way round, and
  leave the command untouched. Rejected: the command still would not use the
  instruments, the pointers would name a command absent on most surfaces, and
  they would add text to two skills that have no reason to know about a
  specific consumer.

## Consequences

- **Upstream drift is accepted.** The fork is pinned at `49dd158`; the
  reference file's header names that commit, so a diff against upstream shows
  what changed since.
- **A local install with the Pocock plugin enabled may show two
  architecture-review commands** — this repo's `improve-codebase` and Pocock's
  `improve-codebase-architecture`. The names differ deliberately, so neither
  shadows the other; which one to keep is the user's plugin choice and is not
  resolved here.
- The vendored `.claude/skills/improve-codebase-architecture/` directory is
  removed and the vendor lock reflects the exclusion. A future re-vendor does
  not bring it back.
- The skill is listed in both catalogue tables, the manifest and the
  `refactoring` plugin, like any other skill. As a command skill it costs no
  always-loaded description budget.
- `refactoring` and `coupling-cohesion` stay unchanged; the dependency points
  from the specific command to the general instruments only.
- `GLOSSARY.md` is not changed: "deepening" and "hotspot" are skill
  vocabulary, not this repo's domain.

## Notes

Deliberately not added to the command, recorded so it is not helpfully
re-added:

- `ddd`, `c4-modeling`, `html-artifacts`, `logical-component-design`,
  `architecture-pattern-advisor`. Each either duplicates a step the command
  already has (the HTML report, the interview) or answers a different question
  (domain modeling, diagrams, decomposing a new system, choosing a topology)
  than "where does deepening pay off in existing code".
- `coupling-cohesion` Mode B, for the reason given above.
- Vendoring Pocock's `codebase-design`, `grilling` or `domain-modeling` into
  `skills/`. The fork carries what it needs in its own reference files.
- Automating the A/B comparison in the eval-suite.

Before re-opening fork vs. patch, check whether the vendored command has become
reachable on every install surface and free of agent-specific vocabulary; until
both hold, the drivers above still apply.
