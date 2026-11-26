---
name: improve-skill
category: refactoring
activation: command
disable-model-invocation: true
environments: coding, chat
argument-hint: "<skill-folder>"
compatibility: Reads one skill folder, in a repo or unpacked from a claude.ai ZIP; git is not required. Writes a snapshot and the rewrite to the OS temp directory; changes the folder, or opens a branch and pull request in a repo, only after the author agrees.
description: Clean AI slop out of one skill folder with numbered slop-signal candidates, an author interview on what is load-bearing, one rewrite, and a rule inventory that blocks delivery if a rule was lost. Use when cleaning up a bloated skill.
metadata:
  version: "0.2"
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Improve Skill

Remove the filler from one skill: text that costs the agent tokens and
attention without changing what it does. The run snapshots the skill, scans it
against the **slop signals**, lists numbered **candidates**, inventories the
skill's rules, interviews the author, rewrites once, and checks the rewrite
against the **rule inventory** before it delivers a unified diff.

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
print that path. The snapshot is the baseline for the check and the way back.

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

## 4. Inventory the rules

List every rule and branch of the snapshot, before anything is rewritten. An
item is anything that changes what the agent does: a step, a constraint, a
condition and each of its branches, a default, an output format, a completion
criterion, a pointer to another file. Definitions, exposition and decoration
are not items. A rule stated in several places is one item citing every line.
The frontmatter is not inventoried: this run leaves it unchanged.

Number the items `R1`, `R2`, … in file and line order and print them:

```markdown
R4 SKILL.md:23-24 Exclude every pull request whose title starts with `chore(deps)`.
```

Done when every imperative or conditional sentence in the snapshot's body
belongs to an item.

## 5. Interview

Interview the author about the candidates in **rounds**, before any file is
written:

1. Ask one numbered question per candidate, except description findings,
   which stay reported only. Give the candidate's proposed action as the
   recommended answer, worded so that "yes" accepts it. Where a candidate
   would remove an `R` item, name the item and ask whether it is
   load-bearing.
2. Ask every question that depends on no open answer in the same round.
   Questions that depend on an open answer, such as which wording of a
   repeated rule to keep, go into the next round.
3. Record each candidate as **accepted** (apply the proposed action),
   **rejected** (leave the text as it is) or **load-bearing** (keep its rule,
   change only its form). Record an `R` item as **struck by author** only
   when an answer strikes it, together with that answer's number. Only an
   interview answer strikes a rule.

Done when every candidate has a recorded decision and the author has
confirmed the printed record.

## 6. Rewrite once

Copy the snapshot to `<tmpdir>/improve-skill-<name>-<timestamp>/new_skill/`
and apply every accepted and load-bearing decision there, in one pass. The
original folder stays untouched until delivery.

- Leave the frontmatter, description included, byte for byte as it was.
- Leave the text of rejected candidates as it was.
- Keep every `R` item that was not struck, in the place the agent needs it
  while acting.

Done when every recorded decision is applied and the frontmatter block of
`new_skill/SKILL.md` matches the snapshot's byte for byte.

## 7. Check the rule inventory

Read `new_skill/` from disk, not from memory of the rewrite, and map each `R`
item to one of:

- the `path:line` in `new_skill/` that carries the rule, with a short quote;
  a rule whose form changed by an accepted candidate maps with that
  candidate's number;
- **struck by author**, with the number of the answer that struck it.

An item with neither is **unmapped**. Print the mapping as a list in `R`
order, then this sentence: "The rule inventory catches lost rules; it cannot
see shifted emphasis or tone."

An unmapped item blocks delivery. Name each one with its snapshot `path:line`
and quote, deliver nothing (no diff as the result, no branch, no commit, no
pull request), and ask the author for each: restore it (copy the rule back
into `new_skill/`, a repair of this rewrite, not a second one) or strike it
(a recorded answer). Then run this check again.

Done when every `R` item is mapped.

## 8. Deliver

Print the unified diff, `diff -ru old_skill new_skill`, then the candidate
decisions and the inventory mapping. Ask the author whether to deliver, and
on "yes":

- **Folder in a git work tree** (`git -C <folder> rev-parse --show-toplevel`
  succeeds): create the branch `improve-skill/<name>` from the current
  branch, copy `new_skill/` over the folder, and commit in the repository's
  commit convention. Push the branch and open a pull request whose body holds
  the candidate decisions, the inventory mapping and the blind-spot sentence.
  Use the GitHub MCP tools if the session has them; otherwise
  `gh api repos/<owner>/<repo>/pulls -f title=<title> -f head=improve-skill/<name> -f base=<base> -f body=<body>`.
  On another forge, use its CLI the same way.
- **Folder outside any git work tree**: copy `new_skill/` over the folder.

Print the snapshot path last: it is the way back.
