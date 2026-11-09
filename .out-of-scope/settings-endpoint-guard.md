# A Hook That Guards Claude Code's Own Settings Against an Endpoint Rewrite

The `secret-guard` plugin does not watch Claude Code's settings files. The
specific mechanism rejected is a `ConfigChange` command hook that blocks a
user, project or local settings change setting `ANTHROPIC_BASE_URL` or
`apiKeyHelper`, so that a planted `CLAUDE.md` cannot send the login token to
an attacker's endpoint. This project keeps it that way.

## Why this is out of scope

The facts below are from the Claude Code docs as read on 2026-11-08 (CLI
2.1.319): the hooks reference (`ConfigChange`), the settings page and the
protected-paths section of the permission-modes page.

**Claude Code already guards these files where it matters.** `.claude/` and
`~/.claude/` are protected paths. A write there prompts in `default` and
`acceptEdits` and is refused in `dontAsk`, and the check covers shell
redirects and `tee`, not only Edit and Write. What is left is `auto` mode,
where a classifier decides, `bypassPermissions`, and writes through an
interpreter (`python -c "open(...)"`). That gap is too narrow to justify
the hook below.

**A guard that would really work is much bigger than the one proposed.** A
`ConfigChange` block only keeps the new settings out of the running
session. The file stays changed on disk and the next session loads it, and
`SessionStart` cannot block. The block is also silent: stderr and `reason`
reach neither the user nor Claude, only the debug log. So a working guard
has to rewrite the user's settings files itself and needs a separate channel
to report a block. That is a model-free hook editing its own harness's
configuration, which costs more than the narrow gap is worth.

**It covers only one harness.** Codex CLI and opencode, which the other
guards cover, have no equivalent event.

If the gap matters on a machine, pinning the endpoint in managed settings
(`managed-settings.json`, highest precedence) is the zero-code option. It
needs root and does not cover `apiKeyHelper`. It is untested here.

## What would reopen it

An endpoint or `apiKeyHelper` rewrite observed in this user's own sessions,
Claude Code dropping `.claude` from its protected paths, or a `ConfigChange`
block that persists on disk or reports to the user.

## Prior requests

- #712: "secret-guard: block agent rewrites of the API endpoint via
  ConfigChange"
