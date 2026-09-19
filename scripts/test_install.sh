#!/usr/bin/env bash
# Smoke test for install.sh. Uses an isolated $HOME under mktemp.
#
# Run: ./scripts/test_install.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL="$REPO_ROOT/install.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "ok: $*"; }

# Number of symlinks in a directory that point into this repo's skills/.
count_our_links() {
  local dir="$1" n=0 f
  [[ -d "$dir" ]] || { echo 0; return; }
  for f in "$dir"/*; do
    [[ -L "$f" ]] || continue
    [[ "$(readlink "$f")" == "$REPO_ROOT/skills/"* ]] && n=$((n + 1))
  done
  echo "$n"
}

# True if a skill is a per-category router (activation: router).
skill_is_router() {
  grep -Eq '^activation:[[:space:]]*router[[:space:]]*$' "$1/SKILL.md" 2>/dev/null
}

skill_is_command() {
  grep -Eq '^activation:[[:space:]]*command[[:space:]]*$' "$1/SKILL.md" 2>/dev/null
}

skill_dir_category() {
  grep -m1 '^category:' "$1/SKILL.md" 2>/dev/null | sed 's/^category://;s/[[:space:]]//g'
}

# Space-padded list of categories that ship a router skill.
ROUTED_CATEGORIES=" "
for _d in "$REPO_ROOT"/skills/*/; do
  [[ -f "$_d/SKILL.md" ]] || continue
  skill_is_router "$_d" && ROUTED_CATEGORIES+="$(skill_dir_category "$_d") "
done

# True if a skill is an auto member nested under a router: a non-router,
# non-command skill whose category is routed.
skill_is_nested_member() {
  skill_is_router "$1" && return 1
  skill_is_command "$1" && return 1
  [[ "$ROUTED_CATEGORIES" == *" $(skill_dir_category "$1") "* ]]
}

FIRST_SKILL=""
FIRST_COMMAND=""
for _d in "$REPO_ROOT"/skills/*/; do
  [[ -f "$_d/SKILL.md" ]] || continue
  [[ -n "$FIRST_SKILL" ]] || FIRST_SKILL="$(basename "$_d")"
  if [[ -z "$FIRST_COMMAND" ]] && skill_is_command "$_d"; then
    FIRST_COMMAND="$(basename "$_d")"
  fi
done
[[ -n "$FIRST_SKILL" ]] || fail "no skills detected in repo"
[[ -n "$FIRST_COMMAND" ]] || fail "no command skill detected in repo"

# Every directory an earlier installer version linked skills into, per target.
legacy_dirs() {
  case "$1" in
    claude)   printf '.claude/skills\n.claude/commands\n' ;;
    codex)    printf '.codex/skills\n.codex/prompts\n' ;;
    opencode) printf '.config/opencode/skills\n.config/opencode/command\n.config/opencode/agent\n' ;;
  esac
}

# Populate $1 the way a pre-ADR-0004 install did: a skill dir link and a
# command SKILL.md link in each legacy directory, plus one foreign symlink and
# one dangling link of ours per directory.
make_legacy_home() {
  local home="$1" target sub dir
  for target in claude codex opencode; do
    while IFS= read -r sub; do
      dir="$home/$sub"
      mkdir -p "$dir"
      ln -s "$REPO_ROOT/skills/$FIRST_SKILL" "$dir/$FIRST_SKILL"
      ln -s "$REPO_ROOT/skills/$FIRST_COMMAND/SKILL.md" "$dir/$FIRST_COMMAND.md"
      ln -s "$REPO_ROOT/skills/removed-skill" "$dir/removed-skill"
      ln -s "$home/foreign-src" "$dir/foreign-skill"
    done < <(legacy_dirs "$target")
  done
  mkdir -p "$home/foreign-src"
}

assert_legacy_links_gone() {
  local home="$1" target="$2" what="$3" sub dir
  while IFS= read -r sub; do
    dir="$home/$sub"
    [[ "$(count_our_links "$dir")" -eq 0 ]] \
      || fail "$what left our skill symlinks in $sub"
    [[ -L "$dir/foreign-skill" ]] || fail "$what removed a foreign symlink in $sub"
  done < <(legacy_dirs "$target")
}

assert_legacy_links_present() {
  local home="$1" target="$2" what="$3" sub
  while IFS= read -r sub; do
    [[ "$(count_our_links "$home/$sub")" -eq 3 ]] \
      || fail "$what touched the skill symlinks in $sub"
  done < <(legacy_dirs "$target")
}

# 1. dry-run for --target=all creates nothing and plans no skill link.
HOME_DRY="$(mktemp -d)"
dry_output="$(HOME="$HOME_DRY" "$INSTALL" --target=all --dry-run 2>&1)"
[[ ! -d "$HOME_DRY/.claude" ]] || fail "dry-run created $HOME_DRY/.claude"
[[ ! -d "$HOME_DRY/.codex" ]] || fail "dry-run created $HOME_DRY/.codex"
[[ ! -d "$HOME_DRY/.config/opencode" ]] || fail "dry-run created $HOME_DRY/.config/opencode"
[[ "$dry_output" != *"ln -s"* && "$dry_output" != *"linked"* ]] \
  || fail "dry-run planned a skill symlink"
[[ "$dry_output" == *"instruction fragments into $HOME_DRY/.claude/CLAUDE.md"* ]] \
  || fail "dry-run did not plan the claude instruction block"
[[ "$dry_output" == *"instruction fragments into $HOME_DRY/.codex/AGENTS.md"* ]] \
  || fail "dry-run did not plan the codex instruction block"
[[ "$dry_output" == *"routed member skills in $HOME_DRY/.codex/config.toml"* ]] \
  || fail "dry-run did not plan the codex member overrides"
[[ "$dry_output" == *"write agent $HOME_DRY/.codex/agents/coupling-analyst.toml"* ]] \
  || fail "dry-run did not plan the codex subagents"
pass "dry-run creates no files and plans no skill symlink"

# 2. install never creates a skills directory or a symlink, on any target.
HOME_A="$(mktemp -d)"
HOME="$HOME_A" "$INSTALL" --target=all >/dev/null
for sub in .claude/skills .claude/commands .codex/skills .codex/prompts \
           .config/opencode/skills .config/opencode/command; do
  [[ ! -e "$HOME_A/$sub" ]] || fail "install created $sub"
done
pass "install links no skills on any target"

# 3. Migration: an upgrade removes every symlink a previous version created
#    under all three agents' skill and command directories — resolving or
#    dangling — and leaves symlinks pointing outside this repo untouched.
HOME_MIG="$(mktemp -d)"
make_legacy_home "$HOME_MIG"
HOME="$HOME_MIG" "$INSTALL" --target=all >/dev/null
for target in claude codex opencode; do
  assert_legacy_links_gone "$HOME_MIG" "$target" "install"
done
pass "install removes a previous version's skill symlinks on all targets"

# 3a. --uninstall performs the same migration.
HOME_MIG_UN="$(mktemp -d)"
make_legacy_home "$HOME_MIG_UN"
HOME="$HOME_MIG_UN" "$INSTALL" --target=all --uninstall >/dev/null
for target in claude codex opencode; do
  assert_legacy_links_gone "$HOME_MIG_UN" "$target" "uninstall"
done
pass "uninstall removes a previous version's skill symlinks on all targets"

# 3b. --target=<one> migrates that agent's directories only, and --dry-run
#     reports the removals without performing them.
HOME_MIG_ONE="$(mktemp -d)"
make_legacy_home "$HOME_MIG_ONE"
dry_output="$(HOME="$HOME_MIG_ONE" "$INSTALL" --target=opencode --dry-run 2>&1)"
[[ "$dry_output" == *"rm $HOME_MIG_ONE/.config/opencode/skills/$FIRST_SKILL"* ]] \
  || fail "dry-run did not plan the legacy symlink removal"
for target in claude codex opencode; do
  assert_legacy_links_present "$HOME_MIG_ONE" "$target" "dry-run"
done
HOME="$HOME_MIG_ONE" "$INSTALL" --target=opencode >/dev/null
assert_legacy_links_gone "$HOME_MIG_ONE" opencode "opencode install"
for target in claude codex; do
  assert_legacy_links_present "$HOME_MIG_ONE" "$target" "opencode install"
done
pass "migration is per target and dry-run only reports it"

# 4. Instructions are composed by default into each agent's global file,
#    inside the managed markers only; hand-written content and a leading
#    @-import survive, and a second run is a no-op.
HOME_INS="$(mktemp -d)"
mkdir -p "$HOME_INS/.claude" "$HOME_INS/.codex"
printf '@RTK.md\nmy own notes\n' >"$HOME_INS/.claude/CLAUDE.md"
cp "$HOME_INS/.claude/CLAUDE.md" "$HOME_INS/claude-before.md"
HOME="$HOME_INS" "$INSTALL" --target=claude >/dev/null
CLAUDE_MD="$HOME_INS/.claude/CLAUDE.md"
[[ "$(head -n1 "$CLAUDE_MD")" == "@RTK.md" ]] || fail "leading @-import not kept on the first line"
grep -q '^my own notes$' "$CLAUDE_MD" || fail "hand-written line lost"
grep -q 'agents instructions (managed by install.sh' "$CLAUDE_MD" || fail "begin marker missing"
grep -q '<!-- <<< agents instructions <<< -->' "$CLAUDE_MD" || fail "end marker missing"
grep -q 'Use uv for Python package development' "$CLAUDE_MD" || fail "fragment body missing"
cp "$CLAUDE_MD" "$HOME_INS/claude-once.md"
HOME="$HOME_INS" "$INSTALL" --target=claude >/dev/null
diff -q "$HOME_INS/claude-once.md" "$CLAUDE_MD" >/dev/null \
  || fail "second run changed the instruction file"
pass "instructions block installs by default and is idempotent"

# 5. --uninstall strips only our block, restoring the file byte for byte.
HOME="$HOME_INS" "$INSTALL" --target=claude --uninstall >/dev/null
diff -q "$HOME_INS/claude-before.md" "$CLAUDE_MD" >/dev/null \
  || fail "uninstall did not restore the original instruction file"
pass "instructions uninstall removes only the managed block"

# 6. codex gets its own file created from nothing; opencode deliberately gets
#    none (it already reads ~/.claude/CLAUDE.md).
HOME_INS2="$(mktemp -d)"
HOME="$HOME_INS2" "$INSTALL" --target=all >/dev/null
[[ -f "$HOME_INS2/.codex/AGENTS.md" ]] || fail "codex AGENTS.md was not created"
grep -q 'Use uv for Python package development' "$HOME_INS2/.codex/AGENTS.md" \
  || fail "codex AGENTS.md has no fragment body"
[[ ! -e "$HOME_INS2/.config/opencode/AGENTS.md" ]] \
  || fail "opencode instruction file written (would duplicate ~/.claude/CLAUDE.md)"
[[ ! -e "$HOME_INS2/.config/opencode" ]] \
  || fail "opencode target created a config directory with nothing to write"
pass "instructions create codex's file and skip opencode on purpose"

# 7. Unbalanced markers (a hand edit) leave the file completely alone, on
#    install and uninstall; --dry-run never writes.
HOME_INS3="$(mktemp -d)"
mkdir -p "$HOME_INS3/.claude"
printf 'notes\n\n<!-- >>> agents instructions (managed by install.sh, do not edit) >>> -->\nstray\n' \
  >"$HOME_INS3/.claude/CLAUDE.md"
cp "$HOME_INS3/.claude/CLAUDE.md" "$HOME_INS3/unbalanced-before.md"
HOME="$HOME_INS3" "$INSTALL" --target=claude >/dev/null 2>&1
diff -q "$HOME_INS3/unbalanced-before.md" "$HOME_INS3/.claude/CLAUDE.md" >/dev/null \
  || fail "unbalanced markers did not protect the file on install"
HOME="$HOME_INS3" "$INSTALL" --target=claude --uninstall >/dev/null 2>&1
diff -q "$HOME_INS3/unbalanced-before.md" "$HOME_INS3/.claude/CLAUDE.md" >/dev/null \
  || fail "unbalanced markers did not protect the file on uninstall"
HOME_INS4="$(mktemp -d)"
HOME="$HOME_INS4" "$INSTALL" --target=codex --dry-run >/dev/null
[[ ! -e "$HOME_INS4/.codex/AGENTS.md" ]] || fail "dry-run wrote an instruction file"
pass "unbalanced markers and dry-run never write instruction files"

# 8. a category without a router or subagents leaves config.toml and the
#    agents directory alone (communication ships neither).
HOME_NOMCP="$(mktemp -d)"
HOME="$HOME_NOMCP" "$INSTALL" --target=codex --category=communication >/dev/null
[[ ! -f "$HOME_NOMCP/.codex/config.toml" ]] \
  || fail "category=communication created config.toml"
[[ ! -d "$HOME_NOMCP/.codex/agents" ]] \
  || fail "category=communication created an agents directory"
[[ -f "$HOME_NOMCP/.codex/AGENTS.md" ]] \
  || fail "category=communication skipped the instruction block"
pass "category without router or subagents writes only the instruction block"

# 9. unbalanced markers (hand-deleted end markers) leave config.toml untouched.
HOME_UNBAL="$(mktemp -d)"
HOME="$HOME_UNBAL" "$INSTALL" --target=codex --category=architecture >/dev/null
CONFIG_UNBAL="$HOME_UNBAL/.codex/config.toml"
grep -vE '^# <<< agents' "$CONFIG_UNBAL" > "$CONFIG_UNBAL.tmp"
printf '\n[precious]\nkeep = true\n' >> "$CONFIG_UNBAL.tmp"
mv "$CONFIG_UNBAL.tmp" "$CONFIG_UNBAL"
before="$(cat "$CONFIG_UNBAL")"
HOME="$HOME_UNBAL" "$INSTALL" --target=codex --category=architecture >/dev/null 2>&1
[[ "$(cat "$CONFIG_UNBAL")" == "$before" ]] \
  || fail "install modified a config with unbalanced markers"
HOME="$HOME_UNBAL" "$INSTALL" --target=codex --category=architecture --uninstall >/dev/null 2>&1
[[ "$(cat "$CONFIG_UNBAL")" == "$before" ]] \
  || fail "uninstall modified a config with unbalanced markers"
pass "unbalanced markers leave config.toml untouched"

# 10. codex install disables every nested router member via [[skills.config]].
#     architecture is routed and has the most members, so it exercises the
#     block best.
HOME_OV="$(mktemp -d)"
HOME="$HOME_OV" "$INSTALL" --target=codex --category=architecture >/dev/null
CONFIG_OV="$HOME_OV/.codex/config.toml"
[[ -f "$CONFIG_OV" ]] || fail "codex install did not create config.toml for overrides"
declare -A OV_DISABLED=()
while IFS= read -r name; do OV_DISABLED["$name"]=1; done < <(
  python3 - "$CONFIG_OV" <<'PY'
import sys, tomllib
with open(sys.argv[1], "rb") as f:
    cfg = tomllib.load(f)
for entry in cfg.get("skills", {}).get("config", []):
    if entry.get("enabled") is False and "name" in entry:
        print(entry["name"])
PY
)
for d in "$REPO_ROOT"/skills/*/; do
  [[ -f "$d/SKILL.md" ]] || continue
  name="$(basename "$d")"
  if [[ "$(skill_dir_category "$d")" != "architecture" ]]; then
    [[ -z "${OV_DISABLED[$name]:-}" ]] || fail "category=architecture disabled $name from another category"
  elif skill_is_router "$d"; then
    [[ -z "${OV_DISABLED[$name]:-}" ]] || fail "override disabled the router $name"
  elif skill_is_nested_member "$d"; then
    [[ -n "${OV_DISABLED[$name]:-}" ]] || fail "nested member $name not disabled in config.toml"
  else
    [[ -z "${OV_DISABLED[$name]:-}" ]] || fail "override disabled the command skill $name"
  fi
done
pass "codex install disables nested router members"

# 11. a routed category writes only the override block — never MCP servers —
#     and reinstalling is byte-identical.
HOME_OV2="$(mktemp -d)"
HOME="$HOME_OV2" "$INSTALL" --target=codex --category=ai-ml >/dev/null
CONFIG_OV2="$HOME_OV2/.codex/config.toml"
[[ -f "$CONFIG_OV2" ]] || fail "routed category=ai-ml created no config.toml"
grep -q '^\[mcp_servers\.' "$CONFIG_OV2" \
  && fail "install wrote mcp_servers into config.toml"
before="$(cat "$CONFIG_OV2")"
HOME="$HOME_OV2" "$INSTALL" --target=codex --category=ai-ml >/dev/null
[[ "$(cat "$CONFIG_OV2")" == "$before" ]] || fail "override registration is not idempotent"
pass "override-only config is written and idempotent"

# 12. uninstall removes the override block but keeps foreign config.
printf '\n[foreign]\nkeep = true\n' >> "$CONFIG_OV2"
HOME="$HOME_OV2" "$INSTALL" --target=codex --category=ai-ml --uninstall >/dev/null
grep -Fxq '[foreign]' "$CONFIG_OV2" || fail "override uninstall dropped foreign config"
grep -q 'skills\.config\|routed-member skill overrides' "$CONFIG_OV2" \
  && fail "override uninstall left our block behind"
pass "override uninstall removes only our block"

# 13. a config left behind by a version that still registered the
#     knowledge-base MCP servers is cleaned up — by install as well as by
#     uninstall — across every legacy category, foreign tables untouched.
make_legacy_mcp_home() {
  local home="$1"
  mkdir -p "$home/.codex"
  printf '%s\n' \
    '[mcp_servers.foreign]' \
    'command = "keep-me"' \
    '' \
    '# >>> agents:architecture MCP servers (managed by install.sh, do not edit) >>>' \
    '[mcp_servers.architecture-kb]' \
    'command = "/gone/bin/python"' \
    '# <<< agents:architecture MCP servers <<<' \
    '' \
    '# >>> agents:refactoring MCP servers (managed by install.sh, do not edit) >>>' \
    '[mcp_servers.refactoring-kb]' \
    'command = "/gone/bin/python"' \
    '# <<< agents:refactoring MCP servers <<<' \
    > "$home/.codex/config.toml"
  mkdir -p "$home/.codex/agents-mcp-runtime/bin"
  : > "$home/.codex/agents-mcp-runtime/bin/python"
}

assert_legacy_mcp_gone() {
  local config="$1" what="$2"
  grep -Fxq '[mcp_servers.foreign]' "$config" \
    || fail "$what dropped a foreign MCP server"
  grep -Fxq 'command = "keep-me"' "$config" \
    || fail "$what dropped the foreign server's body"
  if grep -q 'MCP servers\|mcp_servers\.\(architecture\|refactoring\)-kb' "$config"; then
    fail "$what left a legacy managed MCP block behind"
  fi
}

# Install path: cleanup runs even for a category that never shipped a server.
HOME_LEGACY="$(mktemp -d)"
make_legacy_mcp_home "$HOME_LEGACY"
CONFIG_LEGACY="$HOME_LEGACY/.codex/config.toml"
HOME="$HOME_LEGACY" "$INSTALL" --target=codex --category=ai-ml >/dev/null
assert_legacy_mcp_gone "$CONFIG_LEGACY" "install"
[[ -d "$HOME_LEGACY/.codex/agents-mcp-runtime" ]] \
  && fail "install left the legacy MCP runtime venv behind"
python3 - "$CONFIG_LEGACY" <<'PY' || fail "legacy cleanup left invalid TOML"
import sys, tomllib
with open(sys.argv[1], "rb") as f:
    tomllib.load(f)
PY
before="$(cat "$CONFIG_LEGACY")"
HOME="$HOME_LEGACY" "$INSTALL" --target=codex --category=ai-ml >/dev/null
[[ "$(cat "$CONFIG_LEGACY")" == "$before" ]] || fail "legacy cleanup is not idempotent"
pass "install strips legacy MCP blocks and the runtime venv"

# Uninstall path: same cleanup, and a dry-run changes nothing.
HOME_LEGACY_UN="$(mktemp -d)"
make_legacy_mcp_home "$HOME_LEGACY_UN"
CONFIG_LEGACY_UN="$HOME_LEGACY_UN/.codex/config.toml"
before="$(cat "$CONFIG_LEGACY_UN")"
dry_output="$(HOME="$HOME_LEGACY_UN" "$INSTALL" --target=codex --dry-run 2>&1)"
[[ "$(cat "$CONFIG_LEGACY_UN")" == "$before" ]] \
  || fail "dry-run modified the legacy config"
[[ -d "$HOME_LEGACY_UN/.codex/agents-mcp-runtime" ]] \
  || fail "dry-run removed the legacy runtime venv"
[[ "$dry_output" == *"remove legacy architecture MCP servers"* ]] \
  || fail "dry-run did not plan legacy block removal"
[[ "$dry_output" == *"remove legacy MCP runtime venv"* ]] \
  || fail "dry-run did not plan legacy venv removal"
HOME="$HOME_LEGACY_UN" "$INSTALL" --target=codex --uninstall >/dev/null
assert_legacy_mcp_gone "$CONFIG_LEGACY_UN" "uninstall"
[[ -d "$HOME_LEGACY_UN/.codex/agents-mcp-runtime" ]] \
  && fail "uninstall left the legacy MCP runtime venv behind"
pass "uninstall strips legacy MCP blocks; dry-run only reports them"

# 14. codex install converts plugin subagents to valid custom-agent TOML.
HOME_AG="$(mktemp -d)"
HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture >/dev/null
AGENTS_DIR="$HOME_AG/.codex/agents"
for agent in coupling-analyst cohesion-analyst; do
  [[ -f "$AGENTS_DIR/$agent.toml" ]] || fail "missing $agent.toml"
done
python3 - "$AGENTS_DIR" <<'PY' || fail "agent TOML is invalid or incomplete"
import sys, tomllib
from pathlib import Path
for name in ("coupling-analyst", "cohesion-analyst"):
    with open(Path(sys.argv[1]) / f"{name}.toml", "rb") as f:
        agent = tomllib.load(f)
    assert agent["name"] == name
    assert agent["description"]
    assert agent["developer_instructions"].strip()
    assert "${CLAUDE_PLUGIN_ROOT}" not in agent["developer_instructions"]
PY
pass "codex install converts subagents to valid agent TOML"

# 15. re-running leaves the agent files identical; foreign files survive.
before="$(cat "$AGENTS_DIR/coupling-analyst.toml")"
HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture >/dev/null
[[ "$(cat "$AGENTS_DIR/coupling-analyst.toml")" == "$before" ]] \
  || fail "agent conversion is not idempotent"
printf 'name = "mine"\n' > "$AGENTS_DIR/cohesion-analyst.toml"
HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture >/dev/null 2>&1
grep -Fxq 'name = "mine"' "$AGENTS_DIR/cohesion-analyst.toml" \
  || fail "foreign agent file was overwritten"
pass "agent conversion is idempotent and preserves foreign files"

# 16. uninstall removes generated agents only; foreign files stay.
HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture --uninstall >/dev/null 2>&1
[[ ! -f "$AGENTS_DIR/coupling-analyst.toml" ]] \
  || fail "uninstall left a generated agent file"
[[ -f "$AGENTS_DIR/cohesion-analyst.toml" ]] \
  || fail "uninstall removed a foreign agent file"
pass "uninstall removes only generated agent files"

# 17. a category without agents creates no agents directory.
HOME_NOAG="$(mktemp -d)"
HOME="$HOME_NOAG" "$INSTALL" --target=codex --category=workflow >/dev/null
[[ ! -d "$HOME_NOAG/.codex/agents" ]] \
  || fail "category=workflow created an agents directory"
pass "category without subagents leaves agents directory alone"

# 18. a comma-separated --category list covers both categories' extras.
HOME_MULTI="$(mktemp -d)"
HOME="$HOME_MULTI" "$INSTALL" --target=codex --category=architecture,ai-ml >/dev/null
[[ -f "$HOME_MULTI/.codex/agents/coupling-analyst.toml" ]] \
  || fail "category list dropped the architecture subagents"
grep -q 'name = "ml-project-lifecycle"' "$HOME_MULTI/.codex/config.toml" \
  || fail "category list dropped the ai-ml member overrides"
grep -q 'name = "ddd"' "$HOME_MULTI/.codex/config.toml" \
  || fail "category list dropped the architecture member overrides"
pass "category=architecture,ai-ml writes both categories' extras"

# 19. every flag the installer still accepts selects something: the removed
#     ones and a --category without a codex target are rejected.
reject() {
  local what="$1"; shift
  if HOME="$(mktemp -d)" "$INSTALL" "$@" >/dev/null 2>&1; then
    fail "$what was accepted"
  fi
}
reject "invalid --category=bogus" --target=codex --category=bogus
reject "--category without a codex target" --target=claude --category=architecture
reject "--category with --target=opencode" --target=opencode --category=architecture
reject "removed flag --env" --target=claude --env=chat
reject "removed flag --instructions" --target=claude --instructions
reject "invalid --target" --target=bogus
reject "missing --target" --dry-run
reject "unknown flag" --target=claude --bogus
pass "invalid and removed flags are rejected"

# 20. --help documents exactly the flags the installer accepts.
help_text="$("$INSTALL" --help)"
for flag in --target= --category= --dry-run --uninstall; do
  [[ "$help_text" == *"$flag"* ]] || fail "--help does not mention $flag"
done
for flag in --env= --instructions; do
  [[ "$help_text" != *"$flag"* ]] || fail "--help still mentions the removed flag $flag"
done
pass "--help matches the accepted flags"

echo "all install.sh tests passed"
