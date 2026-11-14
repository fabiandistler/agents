# PR review: reusable workflow and inputs

For the repository maintainer and for whoever writes a PR review caller in
another repository. The jobs, their credentials and the security model are in
the [runbook](pr-review-runbook.md#jobs-and-security-model); the decision to
host the factory as reusable workflows is
[ADR-0018](../adr/0018-reusable-factory-workflows.md).

`.github/workflows/factory-pr-review.yml` (`on: workflow_call`) holds the four
jobs. `.github/workflows/pr-review.yml` keeps the file name, the
`pull_request_target` and `workflow_dispatch` triggers, `permissions: {}` and
one job, `pr-review`, that calls it. The Actions UI and the jobs API therefore
list the jobs as `pr-review / hold`, `pr-review / assess`, `pr-review / review`
and `pr-review / publish`.

- **Scripts.** A called workflow checks out the caller, so every job fetches
  `job.workflow_repository` at `job.workflow_sha` (the repository and commit
  of `factory-pr-review.yml`) into `$RUNNER_TEMP/factory`, outside the
  workspace and without a credential, and runs `scripts/pr_*.py` from there.
  The scripts always match the pinned workflow file.
- **Permission cap.** The calling job grants the union of the called jobs'
  scopes: `contents`, `pull-requests`, `issues` and `statuses`, all `write`.
  Each called job asks for less; a caller that grants less breaks a job.
- **Secret.** `CLAUDE_CODE_OAUTH_TOKEN`, required, passed by name under
  `secrets:`, never with `secrets: inherit`.
- **Contexts.** `github` and `vars` are the caller's. `vars.PR_AUTO_MERGE` is
  set only in this repository, so other callers never plan auto-merge.

| Input | Default | Effect |
| --- | --- | --- |
| `pr`, `dry_run` | `""`, `true` | The caller's dispatch inputs. A pull request event ignores both and writes. |
| `skip_head_prefixes` | `""` | Comma-separated head-branch prefixes (repo-maintenance: `maintenance/`). Such a pull request gets no model call, no publish and no hold, also on a manual run: `assess` reads the head branch from the fetched context (`scripts/pr_skip.py`), and the publisher aborts with `head_skipped`. |
| `standards_path` | `""` | Passed to `pr_review.py --standards`: a path in the caller's base checkout or an absolute runner path ([standards file](#standards-file)). |
| `fail_on_unavailable` | `false` | When `true`, `publish` writes `review:unavailable` as usual and then exits 8, so the run turns red. A `skipped` review (draft, fork) does not fail. |
| `quiet_logs` | `false` | When `true`, neither the log nor the step summary holds the plan JSON, whose sticky comment carries the model's text. |
| `setup_command` | `""` | Runs with `bash -euo pipefail -c` in the caller's base checkout, in the `review` job only, before Claude Code is installed and without the model token. A failure fails the review, which publishes `review:unavailable`. |

This repository passes only `pr` and `dry_run`, so its review behaves as before
the extraction. Another repository's caller pins the reusable workflow to a
full commit SHA:

```yaml
jobs:
  pr-review:
    permissions:
      contents: write
      pull-requests: write
      issues: write
      statuses: write
    uses: fabiandistler/agents/.github/workflows/factory-pr-review.yml@<full commit SHA>
    with:
      pr: ${{ inputs.pr || '' }}
      dry_run: ${{ inputs.dry_run != false }}
      fail_on_unavailable: true
      quiet_logs: true
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

## Standards file

An operator who runs the review scripts for another repository can pass that
repository's coding standards with `pr_review.py --standards FILE`. The bundled
prompt describes no kind of repository; the file can. Its text goes verbatim
into the system prompt, after the bundled prompt, under the heading
`## Repository standards` and one fixed sentence that keeps the untrusted-input
rules and the output format in force. It never enters the payload, and its
bytes come out of the 300,000-byte total budget, so a long file can cut the
payload (the review is then marked partial). This repository's own workflow
passes no standards file; a caller passes one with the `standards_path` input.

- **One file, from the runner.** The file must come from the runner: a base
  checkout or an installed copy, never from the pull request head, which the
  pull request author controls. The script reads only the path given on the
  command line; nothing in the context names a file.
- **Pointers are not resolved.** The review call has no tools, so a line in
  the file that only points to another file (such as
  `instructions/70-code-review-conventions.md`, which points to
  `~/.agents/instructions/70-code-review-conventions.md`) cannot be followed.
  Concatenate the always-on and on-demand fragments you want, the code-review
  conventions in particular, into the one file.
- **Cap and failures.** The file must be valid UTF-8 without NUL bytes, not
  empty or whitespace-only, and at most 65,536 bytes. Any other file (or a
  missing or unreadable one) stops the run with exit 3 and one stderr line
  naming `--standards` and the reason, before any model call and without an
  artifact. A larger file is refused, not truncated: silently dropped rules
  would read as a clean review.
- **The model-free reconstruction needs no `--standards`.** When the review
  job was skipped, the publish job runs `pr_review.py --context` without the
  model token. That yields `skipped` for a draft or fork and `unavailable`
  otherwise; standards cannot change either outcome.

```bash
python3 "$scripts/pr_review.py" --context context.json \
  --standards standards.md --dry-run --output request.json
```

`--dry-run` reports `system_bytes` including the standards text.
