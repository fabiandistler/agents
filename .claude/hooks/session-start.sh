#!/usr/bin/env bash
# SessionStart hook for Claude Code cloud sessions: installs the pinned check
# tools and the prek git hook, so scripts/check_all.sh runs every gate and the
# hooks fire on commit, before push. Idempotent; a second run only verifies.
# Local sessions exit at once: there the developer owns the toolchain.
# Bats exemption: a hook (instructions/45-shell-scripts.md).

set -euo pipefail

[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

log() { echo "session-start: $*" >&2; }

persist_path() {
  export PATH="$1:$PATH"
  [ -z "${CLAUDE_ENV_FILE:-}" ] || echo "export PATH=\"$1:\$PATH\"" >>"$CLAUDE_ENV_FILE"
}

# 1. Python tools (prek, pytest, pyyaml), pinned in one file shared with CI.
# A venv, because the image's Debian-owned PyYAML cannot be upgraded in place;
# its bin/ goes first on PATH, so `python3` there is the one with the tools.
reqs=scripts/check_all.requirements.txt
venv="$HOME/.cache/agents-check-tools"
if [ -f "$reqs" ]; then
  [ -x "$venv/bin/python3" ] || python3 -m venv "$venv"
  "$venv/bin/python3" -m pip install -q --disable-pip-version-check -r "$reqs" >&2
  persist_path "$venv/bin"
else
  log "MISSING $reqs; check tools not installed"
fi

# 2. Go for the gitleaks hook. prek downloads Go from go.dev, which the cloud
# proxy blocks; the same release comes through proxy.golang.org as a Go
# toolchain module. Needs any go binary to bootstrap from.
if command -v go >/dev/null 2>&1; then
  latest="$(curl -fsS https://proxy.golang.org/golang.org/toolchain/@v/list |
    sed -n 's/^v0\.0\.1-go\([0-9.]*\)\.linux-amd64$/\1/p' | sort -V | tail -n 1)"
  if [ -n "$latest" ]; then
    persist_path "$(GOTOOLCHAIN="go$latest" go env GOROOT)/bin"
  else
    log "could not list Go toolchains; the gitleaks hook may fail to install"
  fi
else
  log "MISSING go; the gitleaks hook cannot be built (use SKIP=gitleaks)"
fi

# 3. Git hook plus every hook environment (ruff, ty, shellcheck, shfmt,
# gitleaks at the revs in .pre-commit-config.yaml), so the first commit is fast.
if command -v prek >/dev/null 2>&1; then
  prek install >&2
  prek install-hooks >&2
else
  log "MISSING prek; commit hooks not installed"
fi
