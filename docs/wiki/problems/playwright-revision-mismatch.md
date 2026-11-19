# Python Playwright vs. the cloud image's Chromium

- 2026-11-19: Python Playwright 1.65.1 expected Chromium revision 1254; the
  cloud image ships 1243 at `/opt/pw-browsers`. The smoke-suite agent added a
  custom `--browser-executable` pytest option to work around it.
- 2026-11-19 (retro): avoidable. The image's browser is also reachable as
  Playwright's `chrome` channel; pytest-playwright's built-in
  `--browser-channel chrome` works and the custom option was removed before
  push. CI installs its own Chromium and needs neither.
- For the next agent: in a cloud session, run browser tests with
  `--browser-channel chrome` (Python) or `channel: 'chrome'` (Node); never
  `playwright install` locally.
