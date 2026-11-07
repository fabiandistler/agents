#!/usr/bin/env bats
# install.sh for claude: no skill links, and the migration away from the old
# symlink install.

load install_helper

setup() {
  install_setup
}

# A HOME left by the old symlink install for claude: our skill and command
# links (one dangling), foreign links, and the merge guard in settings.json.
make_claude_symlink_home() {
  local home="$1" foreign_src
  foreign_src="$(mktemp -d)/foreign"
  mkdir "$foreign_src"
  mkdir -p "$home/.claude/skills" "$home/.claude/commands"
  ln -s "$REPO_ROOT/skills/architecture" "$home/.claude/skills/architecture"
  ln -s "$REPO_ROOT/skills/documentation" "$home/.claude/skills/documentation"
  ln -s "$REPO_ROOT/skills/removed-skill" "$home/.claude/skills/removed-skill"
  ln -s "$REPO_ROOT/skills/repo-status/SKILL.md" "$home/.claude/commands/repo-status.md"
  ln -s "$foreign_src" "$home/.claude/skills/foreign-skill"
  ln -s "$foreign_src" "$home/.claude/commands/foreign.md"
  "$PYTHON" - "$home/.claude/settings.json" "$REPO_ROOT" <<'PY'
import json, sys
guard = f'python3 "{sys.argv[2]}/scripts/pr_merge_guard.py" --harness claude'
settings = {
    "model": "opus",
    "hooks": {
        "Stop": [{"hooks": [{"type": "command", "command": "x"}]}],
        "PreToolUse": [{"matcher": "^(Bash|mcp__.*)$", "hooks": [{"type": "command", "command": guard}]}],
    },
}
open(sys.argv[1], "w").write(json.dumps(settings, indent=2) + "\n")
PY
}

# Print how many WARN lines about claude filters install.sh ARGS prints.
claude_filter_warns() {
  local err
  err="$(HOME="$(mktemp -d)" "$INSTALL" "$@" 2>&1 >/dev/null)" ||
    fail "install.sh $* exited non-zero"
  grep -c 'WARN .*no effect for claude' <<<"$err" || true
}

# Links an earlier claude install made for every top-level auto skill.
make_old_claude_skills() {
  local home="$1" d
  mkdir -p "$home/.claude/skills"
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    skill_is_command "$d" && continue
    skill_is_nested_member "$d" && continue
    ln -s "$REPO_ROOT/skills/$(basename "$d")" "$home/.claude/skills/$(basename "$d")"
  done
}

@test "claude install links no skills or commands" {
  # install --target=claude links nothing: Claude gets skills, commands,
  # subagents and the merge guard from the plugin marketplace (#567).
  HOME_C="$(mktemp -d)"
  HOME="$HOME_C" "$INSTALL" --target=claude >/dev/null
  [[ ! -e "$HOME_C/.claude/skills" ]] || fail "claude install created ~/.claude/skills"
  [[ ! -e "$HOME_C/.claude/commands" ]] || fail "claude install created ~/.claude/commands"
  [[ ! -e "$HOME_C/.claude/settings.json" ]] || fail "claude install created settings.json"
}

@test "claude install migrates symlinks and the settings.json guard away" {
  # Migration from a symlink install: every claude run removes our skill and
  # command links (live and dangling) and the old merge-guard entry in
  # settings.json; foreign links and settings stay. A dry-run only reports.
  HOME_MIGC="$(mktemp -d)"
  make_claude_symlink_home "$HOME_MIGC"
  cp "$HOME_MIGC/.claude/settings.json" "$HOME_MIGC/settings-before.json"
  migc_dry="$(HOME="$HOME_MIGC" "$INSTALL" --target=claude --dry-run 2>&1)"
  [[ "$(count_links "$HOME_MIGC/.claude/skills")" -eq 4 ]] || fail "dry-run removed claude skill links"
  diff -q "$HOME_MIGC/settings-before.json" "$HOME_MIGC/.claude/settings.json" >/dev/null ||
    fail "dry-run changed settings.json"
  grep -Fq "[dry-run] remove $HOME_MIGC/.claude/settings.json" <<<"$migc_dry" ||
    fail "dry-run did not plan the settings cleanup"
  HOME="$HOME_MIGC" "$INSTALL" --target=claude >/dev/null
  for gone in skills/architecture skills/documentation skills/removed-skill commands/repo-status.md; do
    [[ ! -L "$HOME_MIGC/.claude/$gone" ]] || fail "migration left ~/.claude/$gone"
  done
  [[ -L "$HOME_MIGC/.claude/skills/foreign-skill" ]] || fail "migration removed a foreign skill link"
  [[ -L "$HOME_MIGC/.claude/commands/foreign.md" ]] || fail "migration removed a foreign command link"
  "$PYTHON" - "$HOME_MIGC/.claude/settings.json" <<'PY' || fail "migration mangled settings.json"
import json, sys
settings = json.load(open(sys.argv[1]))
assert settings["model"] == "opus" and settings["hooks"]["Stop"]
assert "PreToolUse" not in settings["hooks"]
PY
  cp "$HOME_MIGC/.claude/settings.json" "$HOME_MIGC/settings-once.json"
  HOME="$HOME_MIGC" "$INSTALL" --target=claude >/dev/null
  diff -q "$HOME_MIGC/settings-once.json" "$HOME_MIGC/.claude/settings.json" >/dev/null ||
    fail "second claude run changed settings.json"
}

@test "claude uninstall migrates too, ignoring --category" {
  # --uninstall runs the same migration, whatever --category says.
  HOME_MIGU="$(mktemp -d)"
  make_claude_symlink_home "$HOME_MIGU"
  HOME="$HOME_MIGU" "$INSTALL" --target=claude --category=workflow --uninstall >/dev/null
  [[ "$(count_links "$HOME_MIGU/.claude/skills")" -eq 1 ]] || fail "claude uninstall left our skill links"
  [[ "$(count_links "$HOME_MIGU/.claude/commands")" -eq 1 ]] || fail "claude uninstall left our command links"
  ! grep -q pr_merge_guard "$HOME_MIGU/.claude/settings.json" || fail "claude uninstall left the guard entry"
}

@test "migration leaves a non-object settings.json alone" {
  # A settings.json that is not a JSON object is left untouched.
  HOME_BADJ="$(mktemp -d)"
  mkdir -p "$HOME_BADJ/.claude"
  printf '["pr_merge_guard.py"]\n' >"$HOME_BADJ/.claude/settings.json"
  HOME="$HOME_BADJ" "$INSTALL" --target=claude >/dev/null 2>&1
  [[ "$(cat "$HOME_BADJ/.claude/settings.json")" == '["pr_merge_guard.py"]' ]] ||
    fail "migration rewrote a settings.json that is not an object"
}

@test "--env/--category with a claude target warn once, exit code unchanged" {
  # --env or --category with a claude target prints exactly one WARN line
  # (they have no effect there) and keeps the exit code; other targets and a
  # plain claude run stay quiet.
  [[ "$(claude_filter_warns --target=claude --category=workflow)" -eq 1 ]] ||
    fail "--category with --target=claude did not warn once"
  [[ "$(claude_filter_warns --target=all --env=chat --category=workflow --dry-run)" -eq 1 ]] ||
    fail "--env/--category with --target=all did not warn once"
  [[ "$(claude_filter_warns --target=claude)" -eq 0 ]] || fail "plain claude run warned"
  [[ "$(claude_filter_warns --target=opencode --env=chat --dry-run)" -eq 0 ]] ||
    fail "--env with --target=opencode warned about claude"
}

@test "claude migration hands removed skills to an installed opencode" {
  # An earlier opencode install skipped the skills it read from
  # ~/.claude/skills. The claude migration removes those links, so it hands
  # each skill to an installed opencode, except those codex shares (#567).
  OPENCODE_AUTO_EXPECTED="$(skill_count all opencode)"
  OPENCODE_ONLY_AUTO_EXPECTED="$(opencode_only_expected auto)"
  HOME_HAND="$(mktemp -d)"
  make_old_claude_skills "$HOME_HAND"
  mkdir -p "$HOME_HAND/.config/opencode/skills"
  HOME="$HOME_HAND" "$INSTALL" --target=claude --dry-run >/dev/null
  [[ "$(count_links "$HOME_HAND/.config/opencode/skills")" -eq 0 ]] || fail "dry-run handed skills to opencode"
  HOME="$HOME_HAND" "$INSTALL" --target=claude >/dev/null
  [[ "$(count_links "$HOME_HAND/.claude/skills")" -eq 0 ]] || fail "migration left claude skill links"
  got="$(count_links "$HOME_HAND/.config/opencode/skills")"
  [[ "$got" -eq "$OPENCODE_AUTO_EXPECTED" ]] ||
    fail "migration handed $got skills to opencode, expected $OPENCODE_AUTO_EXPECTED"
  HOME_HAND2="$(mktemp -d)"
  make_old_claude_skills "$HOME_HAND2"
  HOME="$HOME_HAND2" "$INSTALL" --target=codex >/dev/null
  mkdir -p "$HOME_HAND2/.config/opencode/skills"
  HOME="$HOME_HAND2" "$INSTALL" --target=claude >/dev/null
  got="$(count_links "$HOME_HAND2/.config/opencode/skills")"
  [[ "$got" -eq "$OPENCODE_ONLY_AUTO_EXPECTED" ]] ||
    fail "migration handed opencode $got skills codex already shares"
  HOME_HAND3="$(mktemp -d)"
  make_old_claude_skills "$HOME_HAND3"
  HOME="$HOME_HAND3" "$INSTALL" --target=claude >/dev/null
  [[ ! -e "$HOME_HAND3/.config/opencode" ]] || fail "migration created opencode's dir without opencode"
}
