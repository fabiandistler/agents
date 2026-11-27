---
name: refactoring
category: refactoring
environments: coding
description: Finds where refactoring is worth starting in an unfamiliar codebase by ranking files by git churn (hotspots) and explaining the ranking. Use when deciding which code to refactor first or where to start cleaning up a legacy repository.
metadata:
  version: "4.1"
---

# Refactoring targets

## When to use

- The user asks which files or modules are worth refactoring first, where the
  hotspots or the technical debt are, or where to begin cleaning up a repo
  nobody in the conversation knows well.
- Not for: how to perform a particular refactoring (technique names and
  mechanics need no help), whether one module or dependency is healthy (that is
  `members/coupling-cohesion/SKILL.md`, read via the `architecture` router),
  staging a risky migration, or test-first development.

## 1. Check that history can answer

The ranking comes from git history, and it lies in four cases. Check them
before running anything:

- **The user already named the target.** Ranking is noise. Pass the file
  itself as `<repo-path>` in step 2 to get only its row and co-changers, then
  read it.
- **Repo younger than the window.** Everything looks hot because everything is
  new; shorten `--since` or rank by size alone.
- **Bulk reformat or license sweep inside the window.** One commit touching
  every file flattens the ranking; narrow `--since` to exclude it.
- **Shallow clone.** History is cut at the clone depth; the script warns when
  it detects one.

## 2. Rank by churn

```
python3 scripts/churn.py <repo-path> [--since '12 months ago'] [--json]
```

Run it from this skill's directory; `<repo-path>` is the repository to rank.
Per file it reports commits in the window, distinct authors, current size,
recency, and one composite score (change frequency × size, Tornhill's hotspot
heuristic). Below the table it lists, for the top hits, the files most often
committed together with them. The docstring explains each column and its
limits; read it before interpreting a number.

## 3. Read the top hits

Treat the output as a reading list, not a work queue. Churn alone is not a
defect: config files, route tables, generated manifests and well-tested
integration points churn because the system is alive. A candidate is a file
that changes often *and* is hard to change safely, and only opening it shows
which. For each top hit, answer two questions:

- **What makes it expensive to change?** Name it concretely with `path:line`
  evidence (a 300-line function, state shared across callers, no tests), or
  say that nothing does.
- **What does it co-change with?** The CO-CHANGES rows answer this. Files that
  keep changing together are one change spread over several files: refactor
  them together, or say why not.

Where structure matters, pair the history signal with a structural one:
`members/coupling-cohesion/SKILL.md`, read via the `architecture` router,
measures how tangled a module is; a file that scores high on both is the
strongest candidate.

**If you can start subagents**, read the top hits in parallel: one subagent per
hit, given the repo path, the file, its co-changers, and the first question.
Each returns a few lines (its verdict with `path:line` evidence), never the
file body. Then rank the candidates yourself; the comparison needs all
verdicts side by side. Without subagents, read the hits one by one.

## 4. Report

Give a short ranked list of candidates, each with the verdict, the evidence,
and the files that change with it. Name the hits you dismissed and why, so the
user can see the ranking was read and not just copied. End with the first
concrete step for the top candidate.

## Once a target is chosen

- **Refactor or change behavior, never in the same step.** A green suite is
  evidence only while external behavior is meant to stay identical. Mix a fix
  into the restructuring and a red test no longer says which one broke.
  Never weaken a failing test to get it green. Finish one, commit, then start
  the other — small committed steps.
- **Characterize before changing untested code.** Tests are the instrument that
  says a refactor preserved behavior. Where coverage is thin, first write tests
  that pin down what the code *currently* does, bugs included. "This needs
  tests around it first" is a complete answer to "can you refactor this."
