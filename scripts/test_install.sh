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
  # Count skills, optionally filtered by environment ($1 = coding|chat|all).
  local want="${1:-all}" n=0
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    if [[ "$want" != "all" ]]; then
      local envs
      envs="$(grep -m1 '^environments:' "$d/SKILL.md" 2>/dev/null | sed 's/^environments://')"
      # Absent field belongs to every environment; otherwise must list $want.
      if [[ -n "${envs//[[:space:]]/}" ]] && [[ ",${envs// /}," != *",$want,"* ]]; then
        continue
      fi
    fi
    n=$((n + 1))
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

# 7. --env=chat links only the chat subset (non-empty, strictly fewer than all).
CHAT_EXPECTED="$(skill_count chat)"
CODING_EXPECTED="$(skill_count coding)"
[[ "$CHAT_EXPECTED" -ge 1 ]] || fail "no chat skills detected"
[[ "$CHAT_EXPECTED" -lt "$EXPECTED" ]] || fail "chat subset is not smaller than all"
HOME_CHAT="$(mktemp -d)"
HOME="$HOME_CHAT" "$INSTALL" --target=claude --env=chat >/dev/null
got="$(count_links "$HOME_CHAT/.claude/skills")"
[[ "$got" -eq "$CHAT_EXPECTED" ]] || fail "env=chat: expected $CHAT_EXPECTED links, got $got"
pass "env=chat links only the $CHAT_EXPECTED chat skills"

# 8. --env=coding links only the coding subset.
HOME_CODE="$(mktemp -d)"
HOME="$HOME_CODE" "$INSTALL" --target=claude --env=coding >/dev/null
got="$(count_links "$HOME_CODE/.claude/skills")"
[[ "$got" -eq "$CODING_EXPECTED" ]] || fail "env=coding: expected $CODING_EXPECTED links, got $got"
pass "env=coding links only the $CODING_EXPECTED coding skills"

# 9. coding + chat cover at least every skill (skills in both are counted twice).
[[ $((CODING_EXPECTED + CHAT_EXPECTED)) -ge "$EXPECTED" ]] \
  || fail "coding ($CODING_EXPECTED) + chat ($CHAT_EXPECTED) < all ($EXPECTED)"
pass "coding + chat subsets cover all skills"

# 10. dry-run with a filter creates nothing.
HOME_DF="$(mktemp -d)"
HOME="$HOME_DF" "$INSTALL" --target=claude --env=chat --dry-run >/dev/null
[[ ! -d "$HOME_DF/.claude" ]] || fail "dry-run --env=chat created $HOME_DF/.claude"
pass "dry-run --env=chat creates no files"

# 11. an invalid --env value is rejected.
if HOME="$(mktemp -d)" "$INSTALL" --target=claude --env=bogus >/dev/null 2>&1; then
  fail "invalid --env=bogus was accepted"
fi
pass "invalid --env is rejected"

echo "all install.sh tests passed"
