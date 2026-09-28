---
title: Task completion
targets: all
---

## Task completion

End every run with two lines:

- **Evidence:** the check command and its result from THIS run (e.g. "testthat 34/34"), plus what it does NOT cover. A subagent's success report is not evidence; the reviewed diff is. "Tests green" does not prove "task done".
- **Assumptions:** every decision the task did not specify (defaults, edge cases, formats, error behavior). If there are none, write "none" explicitly.
