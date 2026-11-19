# Fix agents spend their time on test runs

- 2026-11-19 retro of two tools fix runs (tools#19, 30 min; tools#24, 39 min):
  neither got stuck; most wall time went to tests. The #19 agent ran the full
  suite 4 times (422 s); one tool's tests took 28–38 s. Both waited minutes for CI.
- Trap found the same day: `-k dfbetas-influence` selected only the 3 smoke
  tests and skipped the tool's 31 (file names use underscores). Fixed in
  tools#27: each tool's tests carry both spellings as keywords, guarded by a test.
- A 33,048-input pitch sweep hit the 600 s tool limit and was abandoned
  (tools#24 run). Rule for briefs: time one input first, run long sweeps in the
  background.
- pytest-xdist: 181 tests in 177 s serial, 54 s on 4 workers (retro measurement);
  tools#27 uses it in CI only, because parallel agents share the session's 4 CPUs.

Related: [subagent tool overhead](subagent-tool-overhead.md),
[Playwright revision mismatch](playwright-revision-mismatch.md).
