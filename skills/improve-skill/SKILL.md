---
name: improve-skill
category: refactoring
activation: command
disable-model-invocation: true
environments: coding, chat
argument-hint: "<skill-folder>"
compatibility: Reads one skill folder, in a repo or unpacked from a claude.ai ZIP; git is not required. Writes only a snapshot of the folder to the OS temp directory.
description: Scan one skill folder for AI slop against a fixed list of slop signals and list numbered cleanup candidates, each with a checklist ID and a quote. Use when cleaning up a bloated skill.
metadata:
  version: "0.1"
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Improve Skill

Find the filler in one skill: text that costs the agent tokens and attention
without changing what it does. The run snapshots the skill, scans it against
the **slop signals**, and ends with a numbered list of **candidates**. It edits
no file of the skill.

## When to use

- One skill folder whose body reads bloated: definitions of known things,
  repeated rules, shouted warnings, option menus, decorative sections.
- A skill in a repository, or an unpacked claude.ai skill ZIP outside any
  repository.

Writing a new skill is not this command's job. Neither is improving how a
description triggers: description findings are listed, then handed to
Anthropic's `skill-creator` and its description optimisation.

## 1. Snapshot

The argument is a folder holding a `SKILL.md`. If it does not hold one, stop
and ask for the skill folder.

Before reading any file in it, copy the whole folder into the OS temp
directory as `<tmpdir>/improve-skill-<name>-<timestamp>/old_skill/`, then
print that path. The snapshot is the baseline for later checks and the way
back.

Done when `diff -r <folder> <snapshot>` prints nothing.

## 2. Scan

Read `references/slop-signals.md`. It defines SL1 to SL7: the shape of each
signal, the test that separates slop from a load-bearing line, the proposed
action, and the checklist ID each one maps to.

Read the snapshot, not the original: `SKILL.md` including its frontmatter, and
every Markdown file under `references/`. Take the signals in order, SL1 to
SL7, and walk the full text once per signal. For every hit, record:

- the signal ID and its checklist ID;
- the `path:line`, relative to the skill folder;
- the quoted text, verbatim and short enough to locate it;
- the proposed action from the signal, adjusted by its test. A line that
  passes the test as load-bearing gets a change of form (a reason added, a
  duplicate merged), never removal.

When the skill folder sits in a checkout that has
`docs/agents/skill-audit-checklist.md` at its root, also apply that
checklist's D, B and R items, and record their hits the same way under the
item's ID. A hit that matches both a signal and a checklist item is one
candidate citing both IDs.

Done when every signal and every applied checklist item has been checked
against every file, including the ones with no hit.

## 3. List the candidates

Print the candidates numbered from 1, ordered by file (`SKILL.md` first) and
then by line, so that two runs on the same skill produce the same numbers.
Use this shape:

```markdown
3. SL4/B9 SKILL.md:23
   > IMPORTANT: You MUST NEVER include a pull request whose title starts with
   Keep the rule, state it plainly, add the failure it prevents.
```

A description finding (SL6, or any D item) carries the proposal "Not
rewritten here: take it to `skill-creator`'s description optimisation". This
command never rewrites a description, because a changed trigger would blur
whether the rest of the skill still behaves the same.

After the list, print the snapshot path again and end the run. The original
folder stays as it was.
