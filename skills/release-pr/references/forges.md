# Forges: PR, CI, and release commands per host

`release_state.py` reports `forge` from the remote's URL. Every git step
(commit, tag, push) is the same everywhere; only the steps below differ.
Check the CLI is installed and authenticated before step 6 of prepare, not
after the push. PR title, body order, commit message, and tag name stay as
`SKILL.md` gives them.

## github — `gh`

```bash
gh pr view --json number,url                  # existing PR for this branch?
gh pr create --title "<pkg> X.Y.Z" --body-file /tmp/pr-body.md
gh pr edit --body-file /tmp/pr-body.md
gh run list --commit "$(git rev-parse HEAD)"  # CI on the tagged commit
gh release create vX.Y.Z --verify-tag --title "<pkg> X.Y.Z" --notes-file /tmp/notes.md
```

Issue link in the body: `Closes #<n>`.

## azure — Azure Repos, `az` with the `azure-devops` extension

Installs on first use of `az repos`; sign in with `az login` (or
`az devops login` with a PAT). `--detect` (on by default) reads the
organization and project from the git remote. For a remote it cannot
parse, pass `--org https://dev.azure.com/<org> --project <project>`.

```bash
# existing PR for this branch?
az repos pr list --source-branch "$(git branch --show-current)" --status active \
  --query "[0].pullRequestId" -o tsv
az repos pr create --title "<pkg> X.Y.Z" --description "$(cat /tmp/pr-body.md)" \
  --source-branch "$(git branch --show-current)" --work-items <id>
az repos pr update --id <id> --description "$(cat /tmp/pr-body.md)"
```

- Pass the body as **one** argument. `--description` turns each separate
  value into a new line, so the `$(cat …)` must be quoted.
- **The PR description is capped at 4,000 characters** and the service
  rejects a longer one. Check with `wc -m /tmp/pr-body.md` first. If the body
  is over, cut `### Changes` to its subheadings with one line each and add a
  link to the changelog on the branch. Leave the other sections as they are.
- Link work items with `--work-items` (space separated). `Closes #<n>` does
  nothing here. `#<id>` in the text only mentions the work item.
- Target branch defaults to the repository's default branch. Pass
  `--target-branch` only when it differs.

**CI on the tagged commit.** `az pipelines runs list` cannot filter by
commit, so filter on the branch and match `sourceVersion`:

```bash
az pipelines runs list --branch main --top 20 \
  --query "[?sourceVersion=='$(git rev-parse HEAD)'].{pipeline:definition.name,status:status,result:result}" \
  -o table
```

Every row must be `completed` / `succeeded`. **No row** means no
pipeline ran on the merge commit. That is common in Azure Repos: build
validation under a branch policy runs on the PR's merge ref, and the
pipeline may have no CI trigger on `main`. Report that and show the PR's
last validation run. Tag only after the user confirms. Never count a
missing run as green.

**Release.** Azure Repos has no release object. The annotated tag is the
release. Put the notes in the tag message, and Azure Repos shows them on
the repository's Tags page:

```bash
{ printf '%s X.Y.Z\n\n' "<pkg>"; cat /tmp/notes.md; } > /tmp/tag-msg.md
git tag -a vX.Y.Z -F /tmp/tag-msg.md
git push origin vX.Y.Z
```

This replaces tag steps 5 and 6 of `SKILL.md`. If an Azure Pipeline has a
`tags` trigger (`trigger: tags: include: [v*]`), the push starts it: an
Azure Artifacts feed, a PyPI upload, or a GitHub mirror. Name that
pipeline in the report. The skill does not run it by hand.

PyPI trusted publishing does not accept Azure Pipelines. Its OIDC
providers are GitHub Actions, GitLab CI/CD, Google Cloud, and ActiveState.
A PyPI upload from Azure therefore needs an API token, stored as a secret
pipeline variable, or a GitHub mirror that publishes. Say which one the
repo uses, and do not add a token yourself.

## gitlab — `glab`

```bash
glab mr view                                   # existing MR for this branch?
glab mr create --title "<pkg> X.Y.Z" --description "$(cat /tmp/pr-body.md)" --yes
glab mr update --description "$(cat /tmp/pr-body.md)" --yes
glab api "projects/:id/pipelines?sha=$(git rev-parse HEAD)"   # CI on the commit
glab release create vX.Y.Z --name "<pkg> X.Y.Z" --notes-file /tmp/notes.md
```

Push the annotated tag first (step 5). `glab release create` on a tag
that does not exist creates it from the default branch's tip, and that tip
is not necessarily the verified commit. Issue link in the body:
`Closes #<n>`.

## unknown or none

For Bitbucket, Gitea, a self-hosted server, or no remote, use git only:

- Prepare: push the branch, write the body to `/tmp/pr-body.md`, and give
  the user the file and the branch name to open the PR in the web UI. Do
  not guess a CLI or a REST endpoint.
- Tag: use the annotated tag with notes, as for Azure. The user checks CI
  and confirms it is green before the tag is pushed.
