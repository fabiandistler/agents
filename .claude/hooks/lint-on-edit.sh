#!/usr/bin/env bash
# PostToolUse hook for Edit, Write and MultiEdit: runs the pinned ruff-check
# (--fix) and ruff-format hooks from .pre-commit-config.yaml through prek on
# the edited Python file, so ruff findings reach the model in the same turn
# instead of at the end, in scripts/check_all.sh (#806).
# The first prek run applies the fixes; the second decides the result, because
# prek sees a rewrite only through git and reports an untracked file as passed
# even when it rewrote it.
# Exit 0 silent: not a Python file in this project, or nothing left to fix.
# Exit 2: the second run's output, or the missing-prek line, on stderr; on
# PostToolUse Claude Code shows it to the model and keeps the edit.
# Bats exemption: a hook (instructions/45-shell-scripts.md). Its tests live in
# test/lint_on_edit.bats all the same.

set -euo pipefail

project_dir="$(cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}" && pwd -P)"

file_path="$(python3 -c '
import json, sys
print(json.load(sys.stdin).get("tool_input", {}).get("file_path") or "")
')"

case "$file_path" in
  *.py) ;;
  *) exit 0 ;;
esac

cd "$project_dir"
[ -f "$file_path" ] || exit 0
resolved="$(realpath -- "$file_path")"
case "$resolved" in
  "$project_dir"/*) ;;
  *) exit 0 ;;
esac

if ! command -v prek >/dev/null 2>&1; then
  echo "lint-on-edit: MISSING prek: not installed (python3 -m pip install -r scripts/check_all.requirements.txt)" >&2
  exit 2
fi

prek run ruff-check ruff-format --files "$file_path" >/dev/null 2>&1 || true
if ! findings="$(prek run ruff-check ruff-format --files "$file_path" 2>&1)"; then
  printf '%s\n' "$findings" >&2
  exit 2
fi
