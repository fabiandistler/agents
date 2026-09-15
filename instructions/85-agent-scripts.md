---
title: Scripts an agent runs
targets: all
---

## Scripts an agent runs

Applies to any executable an agent invokes: skill or plugin scripts, hook commands, CI helpers.

- Never read from an interactive prompt. Agents run non-interactive shells; a TTY prompt hangs the session until timeout. Take every input as a flag, env var, or stdin. On a missing required input, exit non-zero naming the flag and its allowed values.
- `--help` is the agent's only interface documentation — one usage line, the flags, two examples. It is also context cost: keep it under ~25 lines.
- Distinct exit code per failure class, documented in `--help`, so the caller can branch without parsing prose. Data to stdout, diagnostics to stderr.
- Bound the output. Harness output is truncated past roughly 10–30k characters, silently. Default to a summary; offer `--output FILE` and `--offset` for the rest.
