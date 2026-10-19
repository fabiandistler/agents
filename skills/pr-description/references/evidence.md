# Running the before/after example

How to run the example for "Vorher / Nachher" on both sides without touching
the user's working tree. Write the example once, keep it minimal, and run the
identical file on both sides.

## Set up and clean up

Never switch the user's working tree. Check the merge-base out into a separate
worktree inside `<run>`, the temporary directory the description goes into.
`PYTHONDONTWRITEBYTECODE=1` keeps `__pycache__/` out of both trees, so the
cleanup below does not trip over it.

```bash
export PYTHONDONTWRITEBYTECODE=1
git worktree add --detach <run>/base "$(git merge-base <base> HEAD)"
```

The PR branch is the user's checkout. When `git status` shows uncommitted
changes, say so in chat and run "Nachher" from a second worktree at `HEAD`.
When done, `git worktree remove --force <run>/base`. `--force` is safe only
on a worktree this run created; never use it on any other.

## R: one reprex per branch

Install each side into its own library, then render the same reprex with that
library first on `.libPaths()`. The child session reprex starts inherits the
library path, so the example stays a plain `library(<pkg>)`.

```bash
mkdir -p <run>/lib-base <run>/lib-pr <run>/vorher <run>/nachher
R CMD INSTALL --library=<run>/lib-base <run>/base
R CMD INSTALL --library=<run>/lib-pr .
cp <run>/example.R <run>/vorher/ && cp <run>/example.R <run>/nachher/
Rscript -e '.libPaths(c("<run>/lib-base", .libPaths())); reprex::reprex(input = "<run>/vorher/example.R", venue = "gh", advertise = FALSE, html_preview = FALSE)'
Rscript -e '.libPaths(c("<run>/lib-pr", .libPaths())); reprex::reprex(input = "<run>/nachher/example.R", venue = "gh", advertise = FALSE, html_preview = FALSE)'
```

Paste each `example_reprex.md` verbatim. An error in "Vorher" is the
evidence: paste it.

## Python: one script per branch

Run the same script from each tree with the project's runner, so imports
resolve against that tree (without uv: `PYTHONPATH=<run>/base/src`):

```bash
uv run --directory <run>/base python <run>/example.py
uv run --directory . python <run>/example.py
```

Paste the script once per side with its output below it.
