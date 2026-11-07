#!/usr/bin/env bats
# install.sh skill filters: --env, --category, and the `targets:` field.

load install_helper

setup() {
  install_setup
}

teardown() {
  # The targets: test adds a fixture skill to this checkout; never leave it.
  rm -rf "$REPO_ROOT/skills/zz-targets-fixture"
}

@test "env=chat links only the chat skills" {
  # --env=chat links only the chat subset (non-empty, strictly fewer than all).
  OPENCODE_EXPECTED="$(opencode_expected)"
  CHAT_EXPECTED=$(($(skill_count chat opencode) + $(command_count chat opencode)))
  [[ "$CHAT_EXPECTED" -ge 1 ]] || fail "no chat skills detected"
  [[ "$CHAT_EXPECTED" -lt "$OPENCODE_EXPECTED" ]] || fail "chat subset is not smaller than all"
  HOME_CHAT="$(mktemp -d)"
  HOME="$HOME_CHAT" "$INSTALL" --target=opencode --env=chat >/dev/null
  got="$(count_links "$HOME_CHAT/.config/opencode/skills")"
  [[ "$got" -eq "$CHAT_EXPECTED" ]] || fail "env=chat: expected $CHAT_EXPECTED links, got $got"
}

@test "env=coding links only the coding skills" {
  # --env=coding links only the coding subset.
  CODING_EXPECTED=$(($(skill_count coding opencode) + $(command_count coding opencode)))
  HOME_CODE="$(mktemp -d)"
  HOME="$HOME_CODE" "$INSTALL" --target=opencode --env=coding >/dev/null
  got="$(count_links "$HOME_CODE/.config/opencode/skills")"
  [[ "$got" -eq "$CODING_EXPECTED" ]] || fail "env=coding: expected $CODING_EXPECTED links, got $got"
}

@test "coding + chat subsets cover all skills" {
  # coding + chat cover at least every skill (skills in both are counted twice).
  OPENCODE_EXPECTED="$(opencode_expected)"
  CHAT_EXPECTED=$(($(skill_count chat opencode) + $(command_count chat opencode)))
  CODING_EXPECTED=$(($(skill_count coding opencode) + $(command_count coding opencode)))
  [[ $((CODING_EXPECTED + CHAT_EXPECTED)) -ge "$OPENCODE_EXPECTED" ]] ||
    fail "coding ($CODING_EXPECTED) + chat ($CHAT_EXPECTED) < all ($OPENCODE_EXPECTED)"
}

@test "dry-run --env=chat creates no files" {
  # dry-run with a filter creates nothing.
  HOME_DF="$(mktemp -d)"
  HOME="$HOME_DF" "$INSTALL" --target=opencode --env=chat --dry-run >/dev/null
  [[ ! -d "$HOME_DF/.config/opencode" ]] || fail "dry-run --env=chat created $HOME_DF/.config/opencode"
}

@test "invalid --env is rejected" {
  # an invalid --env value is rejected.
  if HOME="$(mktemp -d)" "$INSTALL" --target=claude --env=bogus >/dev/null 2>&1; then
    fail "invalid --env=bogus was accepted"
  fi
}

@test "category=architecture links only the architecture skills" {
  # --category links only the matching subset (non-empty, fewer than all).
  OPENCODE_EXPECTED="$(opencode_expected)"
  ARCH_EXPECTED="$(category_count architecture opencode)"
  [[ "$ARCH_EXPECTED" -ge 1 ]] || fail "no architecture skills detected"
  [[ "$ARCH_EXPECTED" -lt "$OPENCODE_EXPECTED" ]] || fail "architecture subset is not smaller than all"
  HOME_CAT="$(mktemp -d)"
  HOME="$HOME_CAT" "$INSTALL" --target=opencode --category=architecture >/dev/null
  got="$(count_links "$HOME_CAT/.config/opencode/skills")"
  [[ "$got" -eq "$ARCH_EXPECTED" ]] || fail "category=architecture: expected $ARCH_EXPECTED links, got $got"
}

@test "category=architecture,refactoring links the union of both" {
  # a comma-separated --category list links the union of both subsets.
  MULTI_EXPECTED="$(category_count architecture,refactoring opencode)"
  HOME_MULTI="$(mktemp -d)"
  HOME="$HOME_MULTI" "$INSTALL" --target=opencode --category=architecture,refactoring >/dev/null
  got="$(count_links "$HOME_MULTI/.config/opencode/skills")"
  [[ "$got" -eq "$MULTI_EXPECTED" ]] || fail "category list: expected $MULTI_EXPECTED links, got $got"
}

@test "invalid --category is rejected" {
  # an invalid --category value is rejected.
  if HOME="$(mktemp -d)" "$INSTALL" --target=claude --category=bogus >/dev/null 2>&1; then
    fail "invalid --category=bogus was accepted"
  fi
}

@test "empty --category is rejected before Bash 3.2 nounset array expansion" {
  # an empty --category value reaches validation on Bash 3.2 with nounset.
  run_install "$(mktemp -d)" --target=claude --category=
  [[ "$status" -eq 2 ]] || fail "empty --category did not exit 2"
  [[ "$output" == *"invalid --category= (expected one of:"* ]] ||
    fail "empty --category did not reach validation"
}

@test "targets: skips excluded agents and prunes a stale link" {
  # A `targets:` skill installs only for the agents it lists. No shipped skill
  # currently uses the field, so exercise it with a temporary fixture skill
  # that opts out of opencode: it must reach codex only — and a stale link
  # in the opencode skills dir is cleaned up by the next install.
  TGT_FIXTURE="$REPO_ROOT/skills/zz-targets-fixture"
  mkdir -p "$TGT_FIXTURE/scripts"
  cat >"$TGT_FIXTURE/SKILL.md" <<'FIXTURE'
---
name: zz-targets-fixture
description: Temporary fixture used by test/install.bats to exercise the targets field.
category: communication
targets: codex
---

# Fixture
FIXTURE
  : >"$TGT_FIXTURE/scripts/bundled.txt"
  HOME_TGT="$(mktemp -d)"
  mkdir -p "$HOME_TGT/.config/opencode/skills"
  ln -s "$TGT_FIXTURE" "$HOME_TGT/.config/opencode/skills/zz-targets-fixture"
  HOME="$HOME_TGT" "$INSTALL" --target=all --category=communication >/dev/null
  [[ ! -e "$HOME_TGT/.config/opencode/skills/zz-targets-fixture" ]] ||
    fail "targets: fixture installed for opencode"
  [[ -f "$HOME_TGT/.agents/skills/zz-targets-fixture/scripts/bundled.txt" ]] ||
    fail "targets: fixture missing (or incomplete) under codex"
  # Its category-mates are unaffected and keep their bundled files.
  [[ -f "$HOME_TGT/.agents/skills/documentation/SKILL.md" ]] ||
    fail "documentation not installed as a whole directory for codex"
  # opencode reads documentation from ~/.agents/skills, so it links no copy (#564).
  [[ ! -e "$HOME_TGT/.config/opencode/skills/documentation" ]] ||
    fail "opencode duplicated documentation, which codex already links"
  # A skill that skips codex is in no root opencode shares, so opencode links it
  # itself (#564).
  sed -i 's/^targets: codex$/targets: opencode/' "$TGT_FIXTURE/SKILL.md"
  HOME_TGT2="$(mktemp -d)"
  HOME="$HOME_TGT2" "$INSTALL" --target=all --category=communication >/dev/null
  [[ -f "$HOME_TGT2/.config/opencode/skills/zz-targets-fixture/scripts/bundled.txt" ]] ||
    fail "targets: fixture excluded from codex got no opencode link"
  [[ ! -e "$HOME_TGT2/.agents/skills/zz-targets-fixture" ]] ||
    fail "targets: fixture excluded from codex was linked for codex"
}
