# ADR-0009: Fork `pr-description` instead of patching the vendored `pr`

## Status

Accepted (2026-10-19).

## Context

Matt Pocock's `pr` skill writes a pull request body: a summary drawn in the
smallest fitting visual (adapted from Dex Horthy's `show-me`), before/after
evidence, and a merge-danger section with door and blast radius. Spec
[#518](https://github.com/fabiandistler/agents/issues/518) needs a PR
description that differs in content and reach: a title as well as a body, plain
German output, a reading order, an executed before/after reprex, named checks
and gaps, and the forge rules of GitHub and Azure DevOps. The question this ADR
answers is *where* that change lives, because `pr` cannot simply be edited
where it sits today:

- It is vendored into `.claude/skills/` by
  `scripts/vendor_mattpocock_skills.py`, which replaces each vendored
  directory wholesale on every re-run (pinned at upstream `49dd158`, v1.3.1).
- The vendored copy reaches Claude cloud sessions in this repo only. It is not
  part of any install surface — not `claude` via the marketplace plugin, not
  `codex`, not `opencode` (ADR-0004).
- A user with Pocock's plugin installed locally already has a skill named `pr`
  from the mattpocock-skills plugin. A catalogue skill of the same name would
  compete with it for the same trigger.

## Decision

Fork `pr` into the catalogue as a new skill,
[`pr-description`](../../skills/pr-description/SKILL.md), in category
`workflow`, `activation: auto`, so it triggers whenever an agent writes a PR
body:

- **Body in English, output in German**, the same split as `was`; English
  output only on explicit request.
- **Pocock's visual catalogue and door/blast-radius vocabulary are kept**, with
  MIT attribution to Matt Pocock (upstream commit `49dd158`, see
  `UPSTREAM-LICENSE`) and credit to Dex Horthy / Humanlayer `show-me`.
- **The skill writes title and body to a file** and never opens the PR.
- **The vendor script's exclusion set gains `pr`.** The vendored
  `.claude/skills/pr/` directory is removed and the vendor lock no longer lists
  it, so cloud sessions in this repo see one PR-description skill, not two.

## Decision drivers

- **Vendor re-runs wipe in-place edits.** The vendor script owns the
  directory; any local change to the vendored `pr` is lost on the next
  re-vendor.
- **The vendored copy reaches cloud sessions only.** A change made there never
  reaches the `claude`, `codex` or `opencode` install surfaces.
- **A distinct name avoids a clash with a locally installed `pr`.** Naming the
  fork `pr-description` keeps it from shadowing, or being shadowed by, Pocock's
  `pr` where his plugin is enabled.
- **The changes are content, not fixes.** ~~German output, the title, the
  reading order and the Azure DevOps rules serve this catalogue's readers;~~
  *Amended 2026-10-19:* the Azure DevOps rules are removed (see Amended below);
  German output, the title and the reading order serve this catalogue's readers;
  they are not changes an upstream English skill would take.

## Considered options

- **Fork into the catalogue (chosen).** One self-contained skill on every
  install surface, under the repo's conventions and CI checks. Costs upstream
  drift (see Consequences).
- **Patch overlay in the vendor script.** Apply a diff to the vendored copy
  after each re-vendor. Rejected: the patch breaks whenever upstream touches
  the same lines, it rewrites most of the skill rather than a few lines, and
  the result still reaches cloud sessions only.
- **Upstream PR to mattpocock/skills.** Rejected: German output, the Azure
  DevOps rules and the reading order are this catalogue's needs, not
  upstream's, and even an accepted PR would leave the `codex` / `opencode`
  reach unsolved here. Out of scope per the spec.
- **Keep both, side by side.** Add `pr-description` and keep vendoring `pr`.
  Rejected: two near-identical auto-triggered skills in cloud sessions let the
  agent pick the English `pr` for the same request.

## Consequences

- **Upstream drift is accepted.** The fork is pinned at `49dd158`; the skill
  names that commit, so a diff against upstream shows what changed since.
- **A local install with the Pocock plugin enabled may show two PR-description
  skills** — this repo's `pr-description` and Pocock's `pr`. The names differ
  deliberately, so neither shadows the other; which one to keep is the user's
  plugin choice and is not resolved here.
- The vendored `.claude/skills/pr/` directory is removed and the vendor lock
  reflects the exclusion. A future re-vendor does not bring it back.
- The skill is listed in both catalogue tables, the manifest and the
  `workflow` plugin, like any other skill. As an auto skill its description
  counts toward the always-loaded budget.
- `release-pr` is not changed and keeps writing its own release body.
- `GLOSSARY.md` is not changed: "PR description" is skill vocabulary, not this
  repo's domain; "Forge" already exists.

## Amended (2026-10-19)

The forge rules are removed
([#528](https://github.com/fabiandistler/agents/issues/528)). `pr-description`
now writes the same title and body on every forge, as upstream `pr` does: no
forge detection, no Azure DevOps reference, no length cap or shortening order,
no work-item syntax, no printed `az` line. Linked issues and an existing PR
body are read with whatever tool the session has for the forge. The reasons are
leanness — the Azure DevOps branch was rarely needed but always loaded — and
forge independence: the branch was untested in practice and partly built on
unverified facts (an undocumented 4,000-character cap, unconfirmed Mermaid on
Azure DevOps Server). The rest of this ADR stands; where the text above names
the Azure DevOps rules as a reason for the fork, the remaining differences
(German output, the title, the reading order, executed evidence) still carry
it. `.out-of-scope/pr-description-forge-rules.md` records what would reopen
the question.

## Notes

Before re-opening fork vs. patch, check whether the vendored `pr` has become
reachable on every install surface and writes the German title and body this
catalogue needs; until both hold, the drivers above still apply.
