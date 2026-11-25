# Claude Code's rm guard breaks Bats tests with a restricted PATH

- 2026-11-25 [read, subagent diagnosis]: in a cloud session, 15 of 39
  dotfiles Bats tests fail locally on main d00e8c6 with `rm: command not
  found`. They pass in CI (`.github/workflows/ci.yml:44-52`, stock
  ubuntu-24.04).
- Cause [read]: the tests symlink `$(type -P rm)` into a private directory and
  run with `PATH=$BIN_DIR:$test_tools` (`test/dotfiles-sync.bats:29-32,78`,
  `test/install-runner-standards.bats:20-23,60`, `fabiandistler/dotfiles@d00e8c6`).
  In a Claude Code session, the Bash tool puts an `rm` guard first on PATH
  (`/root/.claude/rm-guard/<hash>/refuse/rm`, a POSIX sh script). The guard
  runs the next `rm` it finds on PATH. On the tests' PATH there is none, so it
  prints its own "command not found" and exits 127. `/usr/bin/rm` is a real
  GNU coreutils binary.
- Verdict (2026-11-25): no dotfiles fix is needed, because the tests work on
  any ordinary Linux host. The guard is Claude Code's, switched on by a
  server-side flag. None of the maintainer's repos or settings configure it.
  No issue filed. The remedy is a Claude Code bug report: fall back to the real
  `rm` when PATH holds no other one.
- Effect: dotfiles#82 was pushed with `SKIP=bats`. CI's Bats job passed, and
  nothing in dotfiles justified the skip.
- Open: should cloud sessions run the Bats pre-commit hook with the guard
  removed from PATH, or rely on CI alone? This is the maintainer's call.

Related: [consumers without a queue caller](consumers-without-queue.md).
