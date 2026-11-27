# Behaviour eval: `review-decisions-classifier`

> Hand-run eval, not a CI gate: it needs a model. Run it before merging a
> change to `plugins/workflow/agents/review-decisions-classifier.md`.

Four small cases, each a repository tree, an issue and the review decisions
the classifier should return. They cover the prompt's rules that an edit can
drop without any check noticing (#1037): the precedent search and the rule
implemented twice (*What counts*), the Deviation category (*Categories*), a
change with no decision, and the answer format (*Answer*), which
`batches.py merge` parses on every run.

## Contents

- [Cases](#cases)
- [Run a case](#run-a-case)
- [Score](#score)
- [Record a run](#record-a-run)
- [Limits](#limits)

## Cases

Each case lives in `fixtures/<case>/`. The directory name keeps the fixture
code out of the repository's ruff, ty and shellcheck hooks, which skip every
`fixtures/` path.

- `base/`: the repository before the change.
- `change/`: the files the change adds or replaces, copied over `base/`.
- `issue.md`: the issue the change claims to implement.
- `pr.md`: the pull request text, only where the case needs one.
- `expected.md`: the expected decisions and the forbidden ones. Keep it away
  from the classifier; the run step copies only the other files.

| Case | Rule under test | Expected |
| --- | --- | --- |
| `precedent` | precedent search; PR text is a claim, not proof | Public surface in `export.py`, naming `log.py` |
| `rule-twice` | rule implemented twice | Behaviour in `web/signup.js` |
| `deviation` | Deviation category | Deviation in `cleanup.py` |
| `no-decision` | negative case | no card |

## Run a case

Run each case three times, each run with a fresh scratch directory and a
fresh delimiter. The steps follow the skill's *Gather inputs* and *Classify*
sections in `skills/review-decisions/SKILL.md`, without the forge.

1. Build the case repository and its diff. Set `agents` to this repository's
   root and `case` to a case directory name:

   ```bash
   fixtures="$agents/docs/evals/review-decisions-classifier/fixtures"
   scratch="$(mktemp -d)"
   cp -R "$fixtures/$case/base" "$scratch/repo"
   git -C "$scratch/repo" init -q
   git -C "$scratch/repo" add -A
   git -C "$scratch/repo" -c user.name=eval -c user.email=eval@example.invalid commit -qm base
   cp -R "$fixtures/$case/change/." "$scratch/repo/"
   git -C "$scratch/repo" add -A
   git -C "$scratch/repo" -c user.name=eval -c user.email=eval@example.invalid commit -qm change
   git -C "$scratch/repo" diff HEAD~1 HEAD > "$scratch/diff.patch"
   cp "$fixtures/$case/issue.md" "$scratch/"
   if [ -f "$fixtures/$case/pr.md" ]; then cp "$fixtures/$case/pr.md" "$scratch/"; fi
   python3 "$agents/skills/review-decisions/scripts/batches.py" split "$scratch/diff.patch" --out "$scratch/batches"
   python3 -c 'import secrets; print("ANSWER_" + secrets.token_hex(16))'
   ```

   The split must report one batch. The last line is the run's delimiter.

2. Start the `review-decisions-classifier` subagent in a fresh context, with
   the workflow plugin installed or from a session in this repository. Give
   it only this brief, with the paths filled in:

   ```text
   Repository root: <scratch>/repo
   Diff: <scratch>/diff.patch
   Issue: <scratch>/issue.md
   PR text: <scratch>/pr.md   (only when the case has pr.md)
   Conventions: none
   Answer file: <scratch>/batches/batch-1.answer.md
   Heredoc delimiter: <delimiter from step 1>
   ```

   On a runtime without that subagent, start a fresh agent with the body of
   the classifier's definition as its instructions and the same brief.
   The run passes the format check only if it replies
   `Wrote <answer-file>.` and the answer file exists.

3. Parse the answer and print what the score compares:

   ```bash
   python3 "$agents/skills/review-decisions/scripts/batches.py" merge "$scratch/batches" > "$scratch/cards.json"
   jq -r '"deviation: \(.deviation)", "unclassified: \(.unclassified | length)",
     (.cards[] | "\(.category | ascii_downcase)\t\(.location_path)")' "$scratch/cards.json"
   ```

   Read the full cards in `cards.json` for the forbidden decisions and the
   *The card also* column of `expected.md`.

## Score

A run matches its case when all of these hold:

- `unclassified` is 0: the answer parsed. A malformed answer, a missing file
  or a reply other than `Wrote <answer-file>.` fails the run.
- `deviation` is `checked`: every case passes an issue.
- Every row of `expected.md` has a card with that category and file, and the
  card meets the row's *The card also* column.
- No card is one the case forbids. In `no-decision`, any card fails the run.

Extra cards beyond these fail nothing; note them in the record, since a card
the reviewer has to dismiss on every run is noise worth fixing.

A case passes when two of its three runs match. The eval passes when every
case passes.

## Record a run

Add a dated section below, newest first, with the commit of the classifier
prompt, the model and runtime, and per case the matched runs (`2/3`) and any
extra cards. Keep the answer files of a failed run until the prompt is fixed.

### 2026-11-27: baseline

- Classifier prompt: `plugins/workflow/agents/review-decisions-classifier.md`
  at `29c0d07`.
- Runtime: Claude Code 2.1.331, `review-decisions-classifier` subagent with
  no model override, so it ran on the session model, Claude Opus 5.5
  (`claude-opus-5-5`).
- Result: the eval passes. All 12 runs replied `Wrote <answer-file>.`, and
  every answer parsed (`unclassified` 0, `deviation` checked).

| Case | Matched | Extra cards |
| --- | --- | --- |
| `precedent` | 3/3 | every run: a Deviation card (only `OSError` failures are logged), a second Public surface card (event names), a Behaviour card (log and re-raise), a Tests card |
| `rule-twice` | 2/3 | run 2 filed the 30-vs-32 card as Deviation, not Behaviour, so it missed; every run: a Behaviour card on the copied rule and a Tests card |
| `deviation` | 3/3 | run 1: a Public surface card on the dry-run output; runs 2 and 3: a Tests card |
| `no-decision` | 3/3 | none |

Every `precedent` run named `log.py` and called the PR's "no log format"
claim false. A Tests card showed up in 8 of the 9 runs that returned cards,
though no fixture has tests; that is the noise most worth trimming.

## Limits

- Three runs per case catch a rule the prompt dropped, not a rate. A case
  that matches 2 of 3 can still fail one review in three.
- The cases are small and name their rule plainly; a real diff hides the same
  choice among unrelated changes.
- The eval does not run the skill's check for stray writes, does not split a
  diff into batches, and passes no conventions files.
