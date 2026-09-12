---
name: refactoring
category: refactoring
environments: coding
description: Finding where refactoring is worth starting in a codebase nobody knows well — ranks files by git churn (hotspots) and says how to read the ranking. Use when the user asks which code to refactor first or where to begin cleaning up a legacy repo.
metadata:
  version: "4.0"
---

# Refactoring targets

One job: answer "where should we start?" with evidence instead of a guess.

## When to use

- The user asks which files or modules are worth refactoring first, where the
  hotspots are, or where to begin cleaning up a repo nobody in the conversation
  knows well.
- Not for: how to perform a particular refactoring (technique names and
  mechanics need no help), whether one module or dependency is healthy (that is
  `coupling-cohesion`), staging a risky migration, or test-first development.

## Rank by churn, then read

The bundled script ranks files by their git history, the one source of
evidence every repo already has:

```
python3 skills/refactoring/scripts/churn.py [path] [--since '12 months ago'] [--json]
```

Per file it reports commits in the window, distinct authors, current size,
recency, and one composite score (change frequency × size, Tornhill's hotspot
heuristic). The docstring explains each column and its limits; read it before
interpreting a number.

Treat the output as a reading list, not a work queue. Churn on its own is not
a defect: config files, route tables, and well-tested integration points churn
because the system is alive. A candidate is a file that changes often *and* is
hard to change safely, and only opening it shows which. For each top hit, open
it and say concretely what makes it expensive to change, or that nothing does,
before proposing any work. Pair the history signal with a structural one where
it matters: `coupling-cohesion` measures how tangled a module is, and a file
that scores high on both is the strongest candidate.

## When the ranking lies

Skip the script, or discount its output, in these cases:

- **Repo younger than the window.** Everything looks hot because everything is new.
- **Bulk reformat or license sweep inside the window.** One commit touching every file flattens the ranking; narrow `--since` to exclude it.
- **Shallow clone.** History is cut at the clone depth; the script warns when it detects one.
- **The user already named the target.** Ranking is then noise; go read the target.

## Two disciplines once a target is chosen

Reasoned, not measured: these are kept because the failure mode is discipline
under pressure, not missing knowledge.

- **Refactor or change behavior, never in the same step.** A green suite is
  evidence only while external behavior is meant to stay identical. Mix a fix
  into the restructuring and a red test no longer says which one broke.
  Finish one, commit, then start the other.
- **Characterize before changing untested code.** Tests are the instrument that
  says a refactor preserved behavior. Where coverage is thin, first write tests
  that pin down what the code *currently* does, bugs included. "This needs
  tests around it first" is a complete answer to "can you refactor this."

Scope history and what was deliberately cut from this skill:
`docs/adr/0001-refactoring-skill-scope.md`.
