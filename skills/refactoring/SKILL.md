---
name: refactoring
category: refactoring
environments: coding
description: Finding where refactoring is worth starting in a codebase nobody knows well — ranks files by git churn (hotspots) and says how to read the ranking. Use when the user asks which code to refactor first or where to begin cleaning up a legacy repo.
metadata:
  version: "4.1"
---

# Refactoring targets

One job: answer "where should we start?" with evidence instead of a guess.

## When to use

- The user asks which files or modules are worth refactoring first, where the
  hotspots are, or where to begin cleaning up a repo nobody in the conversation
  knows well.
- Not for: how to perform a particular refactoring (technique names and
  mechanics need no help), whether one module or dependency is healthy (that is
  `members/coupling-cohesion/SKILL.md`, read via the `architecture` router),
  staging a risky migration, or test-first development.

## Rank by churn, then read

The bundled script ranks files by their git history, the one source of
evidence every repo already has:

```
python3 <skills-dir>/refactoring/scripts/churn.py [path] [--since '12 months ago'] [--json]
```

`[path]` is the repository to rank (default: the current directory). The
same script is installed under your agent skills directory.
Because the script takes the target as an argument, the command works from
any working directory once installed.

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
it matters: `members/coupling-cohesion/SKILL.md`, read via the `architecture`
router, measures how tangled a module is, and a file that scores high on both is the strongest candidate. For each top hit, list its co-changers with the same `--since` window (`--name-only` with a path shows only that path, so expand the commits first):
`for c in $(git log --since '<window>' --pretty=%H -- <file>); do git show --name-only --pretty=format: $c; done | grep . | sort | uniq -c | sort -rn | head`
Files that co-change are one change, not two: refactor them together, or say why not.

**If you can start subagents**, read the top hits in parallel: one subagent per
hit, given the repo path, the file, the `--since` window, and the two questions
above (what makes it expensive to change, which files co-change with it). Each
returns a few lines — its verdict with `path:line` evidence and the top
co-changers with counts — never the file body. Merge co-changer groups that
overlap across hits, then rank the candidates yourself; the comparison needs
all verdicts side by side. Without subagents, read the hits one by one.

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
  Never weaken a failing test to get it green. Finish one, commit, then start
  the other — small committed steps.
- **Characterize before changing untested code.** Tests are the instrument that
  says a refactor preserved behavior. Where coverage is thin, first write tests
  that pin down what the code *currently* does, bugs included. "This needs
  tests around it first" is a complete answer to "can you refactor this."
