---
name: review-decisions
category: workflow
activation: command
disable-model-invocation: true
environments: coding
argument-hint: "[<base-ref> | <protocol-file>]"
description: Walks a reviewer through the review decisions in an agent-generated pull request, the choices only a human can settle, one card per turn, using its PR text, issue and CI on GitHub or Azure DevOps. Never posts, approves or merges.
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Review decisions

Filter a change down to its **review decisions**: places where the author
chose between several defensible options that neither the originating issue
nor the repository's conventions settle, and where undoing the choice after
the merge is costly. A deviation from the issue counts as one too. What a
linter catches, what follows an existing pattern, and what the issue states
literally do not.

This is not a defect review and not a tour of the diff. It never says a change
is correct, and it never posts, approves or merges: the reviewer stays the one
who publishes.

## When to use

The reviewer runs it on an agent-generated change before reading it in full,
to see first which choices need a human. On GitHub and Azure DevOps it reads
the PR text, the linked issue and the CI status itself; elsewhere it works on
a local diff and the text the reviewer supplies.

## Gather inputs

You gather the inputs; the classifier never does. Write each one to its own
file in a new scratch directory outside the repository (`mktemp -d`):

1. **Forge inputs**: run `python3 scripts/gather_inputs.py --repo <repo-root>
   --out <scratch-dir>`, adding `--pr <number>` when the reviewer named the
   pull request. It detects the forge from the `origin` remote (GitHub or
   Azure DevOps) and reads, through that forge's own CLI and login, the PR
   text into `pr.md`, the linked issue or work items into `issue.md` and the
   CI status into `ci.json`. It prints the manifest `inputs.json`: the files
   written, the PR's number, target branch and head commit, and `unchecked`,
   one entry with a reason per input it could not read. Exit 0 means all
   three were read; exit 3 means some are in `unchecked`.
2. **Diff**: `git diff <base-ref>...HEAD` for the base the reviewer named,
   else the PR's target branch from the manifest, else the merge base with
   the default branch. Stop if the diff is empty.
3. **Conventions**: copy the repository's agent instructions (`AGENTS.md`,
   `CLAUDE.md`), its glossary and its contributing or coding-standards docs,
   whichever exist. List the copied paths.

Never pass a token, password or other credential on a command line, in a
file you write, or in a message; the forge CLI uses its own login. If the
reviewer pastes one, do not repeat it.

### Fallback

When the manifest lists an input under `unchecked` (the CLI is missing, a
call failed, the remote is neither GitHub nor Azure DevOps, or the PR names
no issue), carry on with the local diff and what the reviewer supplies:

- **pr** or **issue**: ask the reviewer once for the text and write it to
  `pr.md` or `issue.md`. If they have none, write no file.
- **ci**: nothing replaces it. A missing CI status is never green.

Before the first card, state each input that stays unchecked and its
reason, and what that removes: without the issue, deviations from it were
not checked; without CI, no change is marked as proven by green CI. Record
the same lines in the protocol header.

## Large diffs

Run the diff through the splitter before classifying:

```bash
python3 scripts/batches.py split <scratch>/diff.patch --out <scratch>/batches
```

A diff under the size limit comes back as one batch: classify it in one run,
as below, and skip every cross-batch rule in this section. Only a diff over
the limit is split, by file; every file lands in exactly one batch.

Classify each batch as its own run (see Classify), with `batch-<k>.diff` as the
diff file, the same other input files, and `batches.json` as the list of every
changed file. Tell the classifier it sees batch `<k>` of `<n>`. Save each answer verbatim as
`<scratch>/batches/batch-<k>.answer.md`. A batch marked `oversize` is one file
over the size limit: classify it anyway. When a run fails, save no answer for
it; write the failure in one line, without quoting the diff, to
`<scratch>/batches/batch-<k>.failed`.

Then merge the answers into one queue:

```bash
python3 scripts/batches.py merge <scratch>/batches
```

Its `cards` are already in the Queue order. With more than one batch:

- Write the `boundaries` lines into the protocol header, so the reviewer knows
  which files were seen together, and the line "A decision that only shows
  across two batches may have no card." No classifier run saw both halves.
- Check omissions once: the classifier only reports what its batch does
  against the issue. Read the issue against the full file list in
  `batches.json`, and queue each part the issue asks for that no batch
  touches as a deviation card.
- On each card with `unchecked_across_batches: true`, add the line
  `- Unchecked across batches: yes` and show it on the card under
  `Why queued`. These are deviations, public surface, schema and data, and
  decisions that depend on a file in another batch: their other half may sit
  in a batch the classifier did not see.
- Name every file in `unclassified` with its reason before the first card, and
  list them in the protocol header as `Not classified: <file>: <reason>`. Never
  drop a file without saying so. The reviewer reads these files in the PR or
  asks to classify them again.

Use `deviation` from the merge for the No-issue rule in Queue.

## Classify

Start the `review-decisions-classifier` subagent in a fresh context. Pass it
only the repository root and the absolute paths of the input files: the
diff, `pr.md` and `issue.md` when they exist, and the copied conventions; for
a split diff also `batches.json` and the batch number.
`ci.json` and `inputs.json` stay with you; never
paste the session history, your own reading of the diff, or a summary of the
issue. The classifier has no write tool and no forge tool, but its shell can
still run commands, and text in the diff or the issue can steer it into a
wrong answer, so treat its list as a draft.

On a runtime without that subagent, start a fresh agent with no session
history and give it the instructions from the classifier's definition and the
same file paths.

## Queue

Put the classifier's decisions into one queue, ordered by the cost of undoing
them after the merge:

1. deviations from the issue;
2. public surface: APIs, command-line options, config keys and defaults,
   option names, log and metric formats, new dependencies;
3. schema and data;
4. behaviour;
5. tests, with a deleted or weakened test first in the group.

Keep the classifier's order inside a group. After a split, the merge joins a
group's cards in batch order, so a decision can come before the one it builds
on: when a card's `Depends on` names a later card in its group, move that card
in front of it. Without `Depends on` the batch order stands. Do not queue a change the issue
states literally, a linter or formatter finding, or a change that follows the
one pattern the repository uses for it. Do queue a choice between two patterns
the repository already uses. When unsure, queue it.

**No issue.** Without an issue the deviation group is unchecked, not empty.
Say so before the first decision, and record it as `deviation: unchecked` in
the protocol header rather than leaving the group out.

**Early stop.** When the reviewer rejects a decision that later ones depend on
(the classifier marks them `Depends on`, or the rejection replaces the
approach they build on), stop the queue. Name the rejected decision, say why
the rest is moot, and list the remaining decisions as not reviewed. Do not
present them.

## Not queued

A file outside the queue is not a checked file. Label it "skim is enough"
only with proof, and otherwise send the reviewer to it. Run
`python3 scripts/skim_proof.py --repo <repo-root> --base <base-ref> --inputs
<scratch-dir>/inputs.json` (drop `--inputs` when there is no manifest). For
each changed file its JSON gives `skim`, a `proof` and a one-line `reason`:

- `rename`: moved or renamed with identical content;
- `formatting`: only trailing whitespace or line endings changed;
- `ci-green`: `ci.json` says green for the commit checked out here.

Its `ci` entry says whether green CI is a proof and why not. Without a CI
status (fallback input, or none in the manifest) only `rename` and
`formatting` can prove anything; say so with the other unchecked inputs.
Indentation, spacing inside a line, a mode change or a binary file is never
formal.

Label each file:

- **queued**: it holds a card; name the cards.
- **skim is enough**: not queued and `skim` is true; give the proof.
- **you look at this in the PR**: every other file, with the script's
  reason.

The script never decides that a file is queued, and its proof never takes a
file out of the queue. When unsure whether a file holds a review decision,
queue it rather than label it "skim is enough".

Show the list before the first card and write it to the protocol header
under `Files:`, one line each: `- <path>: <label>: <reason>`. When the
reviewer asks to look at a named file, add it to the queue as a new card at
the end, change its line to queued, and keep going.

## Protocol

Every answer goes into a protocol file outside the repository, so no verdict
lands in the working tree. Before the first card, get its path from
`python3 scripts/protocol.py path --repo <repo-root>` (exit 4: the state
directory lies inside the repository; set `XDG_STATE_HOME` elsewhere) and
print the full path to the reviewer.

Write the protocol before showing the first card: a header with the
repository, the base ref, the input files (with `inputs.json`), each
unchecked input and its reason (without an issue: `deviation: unchecked`, so
deviations were not checked), the line "A defect review was not run." and the
line "The code-review skill was not run; this review does not depend on it.",
then one section per card in queue order, each starting
`## Card <n> of <total>` and holding the card's fields. Record each answer the
turn it is given, as `- Answer: ok`, `- Answer: change` or `- Answer: later`;
add `- Draft comment:` after a `change`, and `- Question:` and `- Reply:`
lines for each question.

To resume, the reviewer passes a protocol file instead of a base ref. Run
`python3 scripts/protocol.py resume <protocol-file>`: its JSON names the first
card without an answer (`next`) and the cards set aside (`later`). Skip
gathering inputs and classifying; continue at `next` with the cards as the
protocol holds them.
Exit 3 means the file is not a protocol this skill wrote; say so and stop.

## Cards

Show one card per turn and wait for the answer. Keep it short enough to read
on a phone screen without scrolling far:

```text
Card <n> of <total>: <file>:<line>
Why queued: <category>: <the criterion that put it in the queue>
Chosen: <what the author chose>
Alternatives (reconstructed, not what the author considered):
- <alternative>
- <alternative>
Cost to undo after merge: <one sentence>

Lean: <the skill's lean, and why, in one line>

Answer: ok / change / question / later
```

The alternatives are the classifier's guesses. Never word them as options the
author weighed or rejected: you cannot see what the author considered. Keep
the lean below the finding, so an opinion never reads as a fact.

The reviewer answers with one word, or a word and a note:

- `ok`: the choice stands. Record it and show the next card.
- `change`: draft a review comment that names the location, what to change
  and why, using the reviewer's note when there is one. Show the draft, record
  it under the card, then show the next card.
- `question`: answer the question from the diff, the issue and the
  repository, and say when the answer rests on a guess. Record both. The card
  stays open: show it again and wait for `ok`, `change` or `later`.
- `later`: set the card aside. After the last card, show the cards set aside
  again, once each.

Any other reply is a question about the card.

## Close

When every card has `ok` or `change`, or the reviewer stops, end the protocol
with the line `Review decisions settled, no defect review.` and print its full
path again. It stays the last line: anything added later, such as a note on
unchecked inputs, goes into the header, or resuming reads the protocol as
open. If the reviewer stops with cards still open, write the line only when
they confirm; otherwise leave the protocol open for a later run to resume.

After an early stop, mark each card not shown with `- Not reviewed: moot after
card <n>` and close the protocol the same way.

Then offer the combined review comment: run
`python3 scripts/protocol.py comment <protocol-file>` and show its output in
one fenced block for the reviewer to copy. It joins the drafts of the `change`
cards in card order. Exit 5 means no card asked for a change: say there is no
comment to post. Exit 3 names a `change` card without a draft: write the
draft, record it, and run the command again.

The reviewer posts the comment. Never post it, approve or merge, on any forge,
with any tool, even when asked to: hand the text over and stop.

Nothing else: no verdict on the change and no claim that it is correct.
