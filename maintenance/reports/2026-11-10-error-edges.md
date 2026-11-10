# error-edges - 2026-11-10

Baseline before: `SKIP=gitleaks scripts/check_all.sh` -> 0 failed, 0 missing (26 checks
PASS, including pytest, prek, bats). `gitleaks` was skipped as `MAINTENANCE.md` describes; the
`maintenance-gate` job in CI still scans every pull request. After the run only this report
and the run record are added, so the status is unchanged.

**Tooling coverage:** no scanner for this job. Candidates came from `git grep` over `scripts/`,
`scripts/install/`, `plugins/*/scripts/`, `install.sh` and the skill scripts, looking for
`except` clauses, `|| true`, `2>/dev/null`, `check=False` and `errors="ignore"|"replace"`.
Each hit was read in context. ruff `BLE001` (CI gate) covers broad `except` in `.py` files only.

**No PR with code changes.** Every proposal below changes behavior.

This run re-checked the six findings of the 2026-10-13 report (no issue was ever filed for
them and no fix landed). Five still exist. One was resolved and one has no new counterpart.

## Findings

| # | Where | What is swallowed | Impact when it fails | Proposal |
|---|---|---|---|---|
| 1 | `skills/poc-spec-loop/assets/loop.sh:306` | `out=$(run_agent ... \| tee ...) \|\| true` drops the agent's exit status (`set -euo pipefail` is on). | If the agent CLI fails (auth, rate limit, bad flags), the loop runs the item's check on unchanged code and blocks the item after `MAX_ATTEMPTS` with the **check** output as reason. The agent's real error is only in `run_<id>.log`. Every item fails the same way, so up to `MAX_CONSECUTIVE_BLOCKED x MAX_ATTEMPTS` agent calls are spent first. The `\|\| true` itself is intentional (the loop survives); the lost part is the reason. | Capture the status (`out=$(...) && rc=0 \|\| rc=$?`); on `rc != 0` record `agent exited $rc` as the block reason and stop the loop on the first agent failure. |
| 2 | `skills/release-pr/scripts/release_state.py:332-348` (`version_mentions`) | `git grep ... check=False`, only `.stdout` is read. | `git grep` exits 1 for "no match" (fine) and >=2 on error. An error yields an empty `version_mentions`, so the release flow reports nothing stale and outdated version strings survive the release. Likelihood is low: `git()` (line 102) has validated the repo earlier. | Treat `returncode not in (0, 1)` like `git()` does: message on stderr, non-zero exit. |
| 3 | `skills/release-pr/scripts/release_state.py:155` | `except tomllib.TOMLDecodeError: project = None`, then falls through to the regex parser. | The regex fallback exists for Python < 3.11. On 3.11+ it also accepts a **malformed** `pyproject.toml`, so the release state reports a name/version from a file `uv build` will later reject. | On a decode error, report it as a problem (or exit like the other input errors) instead of falling back. |
| 4 | `skills/refactoring/scripts/churn.py:322` (`measure`) | `except OSError: return` leaves `entry.exists = False`. | An unreadable file (permission denied, broken mount) is treated as deleted. Line 517 drops it from `alive`, and `dropped_missing` counts it as missing, so a real hotspot vanishes from the ranking with no hint that it was unreadable. | Separate "missing" from "unreadable": warn on stderr for `OSError`, or count it separately in the output. |
| 5 | `scripts/quick_validate.py:76` | `except OSError: continue` while scanning `SKILL.md` and `references/*.md` for repo-root script paths. | An unreadable reference file is skipped and the check passes. Sibling checks report the same condition as a violation (`scripts/check_reference_tocs.py:57`, `scripts/check_skill_vocab.py:177`: `unreadable: <exc>`), so this one is the odd one out. | Return `f"{label}: unreadable: {exc}"` as a hit, like the siblings. |

## Resolved since 2026-10-13

- Old #2 (`install.sh`, embedded Python `except Exception: sys.exit(1)`): the converter now
  lives in `scripts/plugin_agents.py`, which raises `ValueError` with specific messages and no
  longer swallows them (lines 41-80).

## Checked and not reported

- `scripts/pr_github.py:221-228` (`_diff`): a failed diff request returns status
  `unavailable`, which the risk policy rates high (documented in the docstring). The
  `continue` branches in the base-file loop (lines 176-212) are size and binary limits, not
  errors; a non-404 `FetchError` is re-raised.
- `scripts/pr_merge_guard.py:162-169` (`read_side_file`) returns `""` for an unreadable
  `@file`; the guard then scans nothing from it. The command itself would fail to read that
  file from the same `cwd`, so no merge slips through that the shell would execute. Left as is.
- `scripts/pr_merge_guard.py:270` and `scripts/secret_read_guard.py:267`: on unbalanced quotes
  both fall back to a coarse scan of the text, which is stricter, not weaker.
- `scripts/pr_review_claude.py:93-117`, `scripts/pr_publish.py:262-275`,
  `scripts/check_pr_issue_links.py:149-153`, `scripts/python_init_context.py:154-162`: each
  error becomes a message and a non-zero exit code.
- `scripts/install/*.sh`: `grep ... || true` on marker counts and optional frontmatter
  fields (`selection.sh`, `instructions.sh:258`) are real fallbacks (no match is a valid
  answer; the count is compared afterwards).
- `skills/repo-status/SKILL.md:84-90` (`|| break` on `gh api`) is already tracked in the
  open skill-audit issue #466 (`repo-status:C1`); not filed again.
- Earlier "not reported" entries (`maintenance-scan.sh`, `lcom.py`, `loop.sh:33,84`,
  `release_state.py:81`) were not re-read; none of those files changed in the findings above.
