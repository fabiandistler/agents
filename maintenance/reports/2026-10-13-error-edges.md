# error-edges - 2026-10-13

Baseline before: 13 of 14 checks green (ruff 0.16.10, pytest 84 passed, shellcheck,
`test_install.sh`, all seven `scripts/` checks, `quick_validate.py` on every skill,
`compileall`). `prek run --all-files` was not run, because it can rewrite files. The only
tracked files that changed are this report and `MAINTENANCE.md`, so the check status after
the run matches the baseline.

**Tooling coverage:** this job has no scanner. Candidates come from
`git grep` over the 33 tracked `*.py` / `*.sh` files outside `.claude/`, looking for `except`
clauses, `|| true`, `2>/dev/null`, `check=False` / `returncode`, and `.get(..., default)`.
Each hit was read in context, together with its caller. ruff's `BLE001` covers broad
`except` clauses in `.py` files only. It cannot see Python embedded in a shell heredoc (#2).

**No PR with code changes.** Every proposal below changes behavior.

## Findings

| # | Where | What is swallowed | Impact when it fails | Proposal |
|---|---|---|---|---|
| 1 | `skills/poc-spec-loop/assets/loop.sh:242` | `out=$(run_agent ... \| tee ...) \|\| true` drops the agent's exit status (the script runs with `set -euo pipefail`, line 27). | If the agent CLI fails (auth expired, rate limit, bad `AGENT_FLAGS`), the loop runs the item's check against unchanged code, counts it as a failed attempt, and after `MAX_ATTEMPTS=3` blocks the item with the **check** output as the reason. The agent's real error is only in `run_<id>.log`. Because every item fails the same way, up to `MAX_CONSECUTIVE_BLOCKED x MAX_ATTEMPTS` = 9 agent calls are spent before the loop stops. The `\|\| true` itself is intentional (`6bd8fa7`, so the loop survives); what is lost is the reason. | Capture the status (`out=$(...) && rc=0 \|\| rc=$?`). On `rc != 0`, write `agent exited $rc` to `last_failure_<id>` and the block reason, and stop the loop on the first agent failure instead of burning attempts. |
| 2 | `install.sh:611` (embedded Python in `plugin_agent_toml`) | `except Exception: sys.exit(1)` | The block raises specific messages (`ValueError("missing frontmatter")`, line 577), and they are thrown away. The caller (`install.sh:633`) prints only `WARN failed to convert <md> (skipping)`, so an author whose subagent is not installed for Codex cannot see why. ruff `BLE001` never sees this: it is a heredoc. | Drop the `try/except`. An uncaught exception already exits non-zero with the message on stderr, which the caller lets through, and the WARN line stays. |
| 3 | `skills/release-pr/scripts/release_state.py:324-330` (`version_mentions`) | `git grep ... check=False`, then only `.stdout` is read. | `git grep` exits 1 for "no match" (fine) and >=2 on error. An error gives an empty `version_mentions`. Step "Walk `version_mentions`" in `SKILL.md:160` then reports nothing stale, and outdated version strings survive the release. The likelihood is low because `git()` has already validated the repo by then. | Treat `returncode not in (0, 1)` like `git()` does: message to stderr, exit 4. |
| 4 | `skills/release-pr/scripts/release_state.py:146` | `except tomllib.TOMLDecodeError: project = None`, which falls through to the regex parser. | The regex fallback is meant for Python < 3.11 (comment at line 46). On 3.11+ it also quietly accepts a **malformed** `pyproject.toml`, so the release state reports a name/version read from a file that `uv build` will reject later. | On a decode error, report it as a problem (or exit 3 like the other input errors) instead of falling back. |
| 5 | `skills/refactoring/scripts/churn.py:322` (`measure`) | `except OSError: return` leaves `entry.exists = False`. | An unreadable file (permission denied, broken mount) is treated as deleted. Line 514 drops it from `alive`, so a real hotspot disappears from the ranking with no message. | Separate "missing" from "unreadable": warn on stderr for `OSError` (or mark it unreadable in the output) instead of reusing the deleted-file path. |
| 6 | `scripts/quick_validate.py:76` | `except OSError: continue` while scanning `SKILL.md` and `references/*.md` for repo-root script paths. | An unreadable reference file is skipped and the check passes. The sibling checks report the same condition as a violation (`check_reference_tocs.py:65`, `check_skill_vocab.py:195`: `unreadable: <exc>`), so this one is the odd one out. | Return `f"{label}: unreadable: {exc}"` as a hit, matching the siblings. |

## Checked and not reported

- `install.sh:198-718`: `grep -m1 '^field:' ... 2>/dev/null || true` reads optional
  frontmatter. A missing field is the documented default, so this is a real recovery path.
- `scripts/maintenance-scan.sh:65,101,104`: `|| true` after `pip-audit`, `vulture` and `ruff`.
  Those tools exit non-zero when they find something, and their output goes to stdout
  (`2>&1`), so nothing is hidden.
- `skills/poc-spec-loop/assets/loop.sh:29,79`: the `shopt` probe and the optional remote URL
  are intentional fallbacks.
- `skills/release-pr/scripts/release_state.py:81` (`tag_exact`), `:351` (`forge`): a
  non-zero exit *is* the answer ("no such tag", documented `forge: none`).
- `skills/refactoring/scripts/churn.py:166,175,182,197`: `has_commits` / `is_shallow` /
  `parse_iso` / `valid_since` are predicates whose failure branch is the answer.
- `skills/coupling-cohesion/scripts/lcom.py:130`: `SyntaxError` is reported on stderr and the
  file skipped (documented "reported, not fatal").
- The checker scripts' `except OSError` / `json.JSONDecodeError` handlers in `scripts/check_*.py`
  and `skills/coupling-cohesion/scripts/*.py` all turn the error into a reported violation
  or a non-zero exit.
