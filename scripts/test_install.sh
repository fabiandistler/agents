#!/usr/bin/env bash
# Smoke test for install.sh. Uses an isolated $HOME under mktemp.
#
# Run: ./scripts/test_install.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL="$REPO_ROOT/install.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "ok: $*"; }

with_fake_home() {
  local fake; fake="$(mktemp -d)"
  HOME="$fake" "$@"
  echo "$fake"
}

count_links() {
  # POSIX-portable: -L returns 0 only for symlinks.
  local dir="$1" n=0
  [[ -d "$dir" ]] || { echo 0; return; }
  for f in "$dir"/*; do
    [[ -L "$f" ]] && n=$((n + 1))
  done
  echo "$n"
}

skill_count() {
  local n=0 skip='^(scripts|eval-suite|mcp-wiki-server)$'
  for d in "$REPO_ROOT"/*/; do
    local name; name="$(basename "$d")"
    [[ "$name" =~ $skip ]] && continue
    [[ -f "$d/SKILL.md" ]] && n=$((n + 1))
  done
  echo "$n"
}

EXPECTED="$(skill_count)"
[[ "$EXPECTED" -ge 1 ]] || fail "no skills detected in repo"

# 1. dry-run for --target=all should not create anything.
HOME_DRY="$(mktemp -d)"
HOME="$HOME_DRY" "$INSTALL" --target=all --dry-run >/dev/null
[[ ! -d "$HOME_DRY/.claude" ]] || fail "dry-run created $HOME_DRY/.claude"
[[ ! -d "$HOME_DRY/.codex" ]] || fail "dry-run created $HOME_DRY/.codex"
[[ ! -d "$HOME_DRY/.config/opencode" ]] || fail "dry-run created $HOME_DRY/.config/opencode"
pass "dry-run creates no files"

# 2. install --target=claude links every skill exactly once.
HOME_C="$(mktemp -d)"
HOME="$HOME_C" "$INSTALL" --target=claude >/dev/null
got="$(count_links "$HOME_C/.claude/skills")"
[[ "$got" -eq "$EXPECTED" ]] || fail "claude install: expected $EXPECTED links, got $got"
pass "claude install creates $EXPECTED symlinks"

# 3. Re-running is idempotent (still exactly $EXPECTED links).
HOME="$HOME_C" "$INSTALL" --target=claude >/dev/null
got="$(count_links "$HOME_C/.claude/skills")"
[[ "$got" -eq "$EXPECTED" ]] || fail "idempotent run: link count drifted to $got"
pass "claude install is idempotent"

# 4. Foreign symlink is preserved.
mkdir -p "$HOME_C/.claude/skills"
foreign_src="$(mktemp -d)/foreign"
mkdir "$foreign_src"
ln -sfn "$foreign_src" "$HOME_C/.claude/skills/foreign-skill"
HOME="$HOME_C" "$INSTALL" --target=claude --uninstall >/dev/null
[[ -L "$HOME_C/.claude/skills/foreign-skill" ]] || fail "uninstall removed a foreign symlink"
pass "uninstall preserves foreign symlinks"

# 5. Uninstall removes our symlinks; foreign stays.
ours_remaining=0
for f in "$HOME_C/.claude/skills"/*; do
  [[ -L "$f" ]] || continue
  target="$(readlink "$f")"
  [[ "$target" == "$REPO_ROOT/"* ]] && ours_remaining=$((ours_remaining + 1))
done
[[ "$ours_remaining" -eq 0 ]] || fail "uninstall left $ours_remaining of our symlinks"
pass "uninstall removes our symlinks only"

# 6. install --target=all populates all three roots.
HOME_A="$(mktemp -d)"
HOME="$HOME_A" "$INSTALL" --target=all >/dev/null
for sub in ".claude/skills" ".codex/skills" ".config/opencode/agent"; do
  got="$(count_links "$HOME_A/$sub")"
  [[ "$got" -eq "$EXPECTED" ]] || fail "all install: $sub has $got links, expected $EXPECTED"
done
pass "all install populates claude, codex, opencode"

echo "all install.sh tests passed"
