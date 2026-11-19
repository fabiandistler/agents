# The tools gallery had no checks

- As of `fabiandistler/tools@8b99d6e` (2026-09-15) the repo had no tests, no
  PR check and no hooks. `.github/workflows/static.yml` uploaded the whole repo
  root to Pages on every push to `main`.
- 2026-11-19: the user reported that `data-workflow.html` showed nothing at the
  end. Cause: `goToStep` built the id `stepresult`, the element is `result`; a
  `TypeError` hid every step on all 60 end paths since the file's first commit
  `ea5d802` (2026-04-19). Fixed in `fabiandistler/tools@f07c5d8` (PR tools#10).
- Earlier sign (2026-08-08): PR tools#7 repaired pitch detection on the iPhone
  after release; the 2026-11-19 audit found that fix itself regressed notes
  above ~1.1 kHz by an octave.
- 2026-11-19: the [audit](../snapshots/2026-11-19-tools-audit.md) found an XSS in
  `tool-pattern.html` that could read API keys every gallery page shares through
  the `fabiandistler.github.io` origin. Fixed in `fabiandistler/tools@98c0009`.
- 2026-11-19: a smoke suite and deploy gate were built in PR tools#17 (decision in
  [2026-11-19 decisions](../decisions/2026-11-19-tools-decisions.md)). It
  catches crashes like the data-workflow bug (65 of 66 tests fail on
  `ea5d802`), but none of the open audit bugs: most are silently wrong results
  after interaction, and the suite checks only the first load (retro
  2026-11-19). Fixes therefore ship their repro as a test.
