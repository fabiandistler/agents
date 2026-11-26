---
name: improve-skill
category: refactoring
activation: command
disable-model-invocation: true
environments: coding, chat
argument-hint: "<skill-folder>"
compatibility: Reads one skill folder, in a repo or unpacked from a claude.ai ZIP; git is not required. Writes a snapshot and the rewrite to the OS temp directory; changes the folder and packs a new archive beside the old claude.ai ZIP, or opens a branch and pull request in a repo, only after the author agrees. Eval mode needs Claude Code with Anthropic's skill-creator installed; elsewhere the rule inventory is the only check and behavior is verified by hand.
description: Clean AI slop out of one skill folder with numbered slop-signal candidates, an author interview on what is load-bearing, one rewrite, and a rule inventory that blocks delivery if a rule was lost. Use when cleaning up a bloated skill.
metadata:
  version: "0.4"
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Improve Skill

Remove the filler from one skill: text that costs the agent tokens and
attention without changing what it does. The run snapshots the skill, scans it
against the **slop signals**, lists numbered **candidates**, inventories the
skill's rules, interviews the author, rewrites once, and checks the rewrite
against the **rule inventory** before it delivers a unified diff. In **eval
mode** a **behavior diff** also runs the snapshot and the rewrite against the
same prompts through Anthropic's `skill-creator`.

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
- the quoted text, verbatim in the skill's own language and short enough to
  locate it;
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
   which stay reported only. State the recommended decision (accepted, or
   load-bearing when the signal's test says the line carries a rule) with
   the `R` items it touches, worded so that a single "yes" accepts it.
   Where the action adds a reason, ask the author for the failure the rule
   prevents; the reason is the author's, never invented.
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
- Write in the skill's own language; a German skill stays German.
- Keep every `R` item that was not struck, in the place the agent needs it
  while acting.

Done when every recorded decision is applied and the frontmatter block of
`new_skill/SKILL.md` matches the snapshot's byte for byte.

## 7. Check

The rule inventory runs on every rewrite. Eval mode runs after it when the
author asked for it with the command or accepts it when proposed.

### Rule inventory

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

### Propose eval mode

If the author has not asked for eval mode, propose it when either holds, and
name which:

- **An eval covers a touched rule.** A rule is touched when it maps with a
  candidate number or is struck by author. It is covered when a prompt or
  expected behavior in `old_skill/evals.json` (`should_trigger`,
  `expected_behavior`) or `old_skill/evals/evals.json` (`skill-creator`'s
  `prompt`, `expected_output`, `expectations`) exercises what the rule
  governs.
- **More than a third of the words go.** Count the words of `SKILL.md`
  without its frontmatter plus every Markdown file under `references/`, in
  `old_skill/` and in `new_skill/`; propose when the new count is below
  two thirds of the old.

When neither holds, propose nothing: the rule inventory is the check.

### Eval mode

Eval mode needs `skill-creator` among the session's skills and subagents to
run the two versions apart, as in Claude Code. In claude.ai `skill-creator`
skips its baseline runs, so there is nothing to compare. When either is
missing, run no behavior check: print the note below, carry it into what
step 8 delivers (the pull request body in a repository), and go on to step 8
with the rule inventory as the only check.

```markdown
Behavior not checked: eval mode needs skill-creator and subagents, which this
session lacks. Verify the behavior by hand: run <prompts> once with old_skill/
and once with new_skill/ and compare the results.
```

Otherwise follow `skill-creator`'s "Running and evaluating test cases" in its
case for improving an existing skill, set up as follows:

- Workspace: `<tmpdir>/improve-skill-<name>-<timestamp>/evals/`, so nothing is
  written beside the skill folder.
- The with-skill runs use `new_skill/`. The baseline runs use `old_skill/`:
  the snapshot of step 1 is the `skill-creator` snapshot, so skip its copy.
- Prompts: those of `old_skill/evals/evals.json` with its expectations as
  assertions; else every `should_trigger` prompt of `old_skill/evals.json`,
  with assertions drafted from `expected_behavior`; else two or three
  prompts the author confirms that exercise the touched rules.
- Grade every run with its grader and aggregate the benchmark. Skip its
  viewer and its iteration loop; the comparison below replaces them.

Print a table per prompt: each assertion with its result for `old_skill` and
for `new_skill`. A **deviation** is an assertion that passed for `old_skill`
and failed for `new_skill`. For each deviation name the prompt, the
assertion, and the section of `new_skill/` that governs it (heading and
`path:line`), then list the candidates whose snapshot lines fall in that
section. Deliver nothing. Ask again about those candidates only, as in step 5;
the author may also accept a deviation as intended, a recorded answer. Apply
the changed answers to `new_skill/` as a repair of this rewrite, run the rule
inventory again, and rerun only the deviating prompts on `new_skill/`.

An assertion that failed for `old_skill` and passes for `new_skill` is a gain:
report it, it does not block.

Done when no deviation is open. Carry the tables into what step 8 prints and
delivers (the pull request body in a repository).

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
- **Folder outside any git work tree** (an unpacked claude.ai skill): copy
  `new_skill/` over the folder; the run creates no repository. Then pack it
  for claude.ai with the packager of Anthropic's `skill-creator`:
  1. Ask for the path of the **old ZIP**, the export the folder was unpacked
     from, and record its `sha256sum`.
  2. Copy `new_skill/` to `<tmpdir>/improve-skill-<name>-<timestamp>/package/<name>/`,
     `<name>` being the frontmatter `name`: the packager names the archive
     and its top folder after the folder it packs.
  3. Find the installed packager, `<skill-creator>/scripts/package_skill.py`;
     it needs Python with PyYAML. In `<skill-creator>`, run
     `python -m scripts.package_skill <package-dir>/<name> <old-zip-dir>`.
     It validates the frontmatter and writes `<name>.skill`, a ZIP archive.
     If `<old-zip-dir>/<name>.skill` already exists, pass
     `<old-zip-dir>/improve-skill-<timestamp>` as the output directory so
     nothing is overwritten. A validation failure is a frontmatter finding:
     print it and hand it to `skill-creator`, as with description findings.
     Without an installed `skill-creator` packager, say so: the updated
     folder is the result, for the author to zip by hand.
  4. If the author no longer has the old ZIP, pack the snapshot the same way
     (staged as `<name>/`) into `<output-dir>/old/` as the way back.

  Done when the new archive exists and the old ZIP's `sha256sum` is
  unchanged. Print both archive paths and tell the author: upload the new
  archive in claude.ai's skill settings by hand (rename it to `.zip` if the
  upload asks for one; the format is the same); to roll back, upload the old
  ZIP the same way.

Print the snapshot path last: it is the way back.
