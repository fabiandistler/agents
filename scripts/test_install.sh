#!/usr/bin/env bash
# Smoke test for install.sh. Uses an isolated $HOME under mktemp.
#
# Run: ./scripts/test_install.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL="$REPO_ROOT/install.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "ok: $*"; }

count_links() {
  # POSIX-portable: -L returns 0 only for symlinks.
  local dir="$1" n=0
  [[ -d "$dir" ]] || { echo 0; return; }
  for f in "$dir"/*; do
    [[ -L "$f" ]] && n=$((n + 1))
  done
  echo "$n"
}

# True if a skill's frontmatter marks it `activation: command` (routed to the
# command directory, not the skills directory).
skill_is_command() {
  grep -Eq '^activation:[[:space:]]*command[[:space:]]*$' "$1/SKILL.md" 2>/dev/null
}

# True if a skill is a per-category router (activation: router).
skill_is_router() {
  grep -Eq '^activation:[[:space:]]*router[[:space:]]*$' "$1/SKILL.md" 2>/dev/null
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

# True if a skill is an auto member nested under a router (not linked at top
# level): a non-router, non-command skill whose category is routed.
skill_is_nested_member() {
  skill_is_router "$1" && return 1
  skill_is_command "$1" && return 1
  [[ "$ROUTED_CATEGORIES" == *" $(skill_dir_category "$1") "* ]]
}

# True if a skill is installed for the given target ($2). A skill without a
# `targets:` field belongs to every target.
skill_matches_target() {
  local targets
  targets="$(grep -m1 '^targets:' "$1/SKILL.md" 2>/dev/null | sed 's/^targets://')"
  [[ -z "${targets//[[:space:]]/}" ]] && return 0
  [[ ",${targets// /}," == *",$2,"* ]]
}

skill_count() {
  # Count auto-triggered skills (those linked into the skills dir), optionally
  # filtered by environment ($1 = coding|chat|all) and target ($2, default
  # claude — skills may opt out of a target via `targets:`).
  local want="${1:-all}" target="${2:-claude}" n=0
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    skill_is_command "$d" && continue
    # Nested members ride under their router, so they are not linked flat.
    skill_is_nested_member "$d" && continue
    skill_matches_target "$d" "$target" || continue
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

command_count() {
  # Count `activation: command` skills (routed to the command dir), optionally
  # filtered by environment ($1 = coding|chat|all) and target ($2, default
  # claude).
  local want="${1:-all}" target="${2:-claude}" n=0
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    skill_is_command "$d" || continue
    skill_matches_target "$d" "$target" || continue
    if [[ "$want" != "all" ]]; then
      local envs
      envs="$(grep -m1 '^environments:' "$d/SKILL.md" 2>/dev/null | sed 's/^environments://')"
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
CMD_EXPECTED="$(command_count all)"
[[ "$CMD_EXPECTED" -ge 1 ]] || fail "no command skills detected in repo"
# Skills may opt out of a target via `targets:`, so each target has its own
# expected link count.
CODEX_EXPECTED="$(skill_count all codex)"
OPENCODE_EXPECTED="$(skill_count all opencode)"
CODEX_CMD_EXPECTED="$(command_count all codex)"
OPENCODE_CMD_EXPECTED="$(command_count all opencode)"

# 1. dry-run for --target=all should not create anything.
HOME_DRY="$(mktemp -d)"
HOME="$HOME_DRY" "$INSTALL" --target=all --dry-run >/dev/null
[[ ! -d "$HOME_DRY/.claude" ]] || fail "dry-run created $HOME_DRY/.claude"
[[ ! -d "$HOME_DRY/.codex" ]] || fail "dry-run created $HOME_DRY/.codex"
[[ ! -d "$HOME_DRY/.config/opencode" ]] || fail "dry-run created $HOME_DRY/.config/opencode"
pass "dry-run creates no files"

# 2. install --target=claude links every auto skill into skills/ and every
#    command skill into commands/.
HOME_C="$(mktemp -d)"
HOME="$HOME_C" "$INSTALL" --target=claude >/dev/null
got="$(count_links "$HOME_C/.claude/skills")"
[[ "$got" -eq "$EXPECTED" ]] || fail "claude install: expected $EXPECTED links, got $got"
pass "claude install creates $EXPECTED skill symlinks"
got="$(count_links "$HOME_C/.claude/commands")"
[[ "$got" -eq "$CMD_EXPECTED" ]] || fail "claude install: expected $CMD_EXPECTED command links, got $got"
# A command skill must land as <name>.md in commands/, not in skills/.
[[ -L "$HOME_C/.claude/commands/repo-status.md" ]] || fail "command skill repo-status not linked into commands/"
[[ ! -e "$HOME_C/.claude/skills/repo-status" ]] || fail "command skill repo-status leaked into skills/"
pass "claude install routes $CMD_EXPECTED command skills to commands/"

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

# 6. install --target=all populates all three roots. claude and opencode keep
#    command skills in their command dir; codex has no command dir, so its
#    command skills land in the skills dir instead.
CODEX_SKILLS_EXPECTED=$((CODEX_EXPECTED + CODEX_CMD_EXPECTED))
HOME_A="$(mktemp -d)"
HOME="$HOME_A" "$INSTALL" --target=all >/dev/null
got="$(count_links "$HOME_A/.claude/skills")"
[[ "$got" -eq "$EXPECTED" ]] || fail "all install: .claude/skills has $got links, expected $EXPECTED"
got="$(count_links "$HOME_A/.config/opencode/skills")"
[[ "$got" -eq "$OPENCODE_EXPECTED" ]] \
  || fail "all install: opencode skills has $got links, expected $OPENCODE_EXPECTED"
got="$(count_links "$HOME_A/.codex/skills")"
[[ "$got" -eq "$CODEX_SKILLS_EXPECTED" ]] \
  || fail "all install: .codex/skills has $got links, expected $CODEX_SKILLS_EXPECTED"
got="$(count_links "$HOME_A/.claude/commands")"
[[ "$got" -eq "$CMD_EXPECTED" ]] || fail "all install: claude commands has $got links, expected $CMD_EXPECTED"
got="$(count_links "$HOME_A/.config/opencode/command")"
[[ "$got" -eq "$OPENCODE_CMD_EXPECTED" ]] \
  || fail "all install: opencode command has $got links, expected $OPENCODE_CMD_EXPECTED"
[[ -L "$HOME_A/.codex/skills/repo-status" ]] || fail "codex: command skill repo-status not linked into skills/"
[[ -f "$HOME_A/.codex/skills/repo-status/agents/openai.yaml" ]] \
  || fail "codex: command skill repo-status missing its openai.yaml sidecar"
[[ ! -e "$HOME_A/.codex/prompts/repo-status.md" ]] || fail "codex: command skill repo-status leaked into deprecated prompts/"
pass "all install populates claude, codex, opencode (codex commands as skills)"

# 6a. --uninstall removes command-dir links (and the codex skill links).
HOME="$HOME_A" "$INSTALL" --target=all --uninstall >/dev/null
for sub in ".claude/commands" ".config/opencode/command"; do
  got="$(count_links "$HOME_A/$sub")"
  [[ "$got" -eq 0 ]] || fail "all uninstall: $sub still has $got command links"
done
[[ ! -e "$HOME_A/.codex/skills/repo-status" ]] || fail "codex uninstall left command skill repo-status behind"
pass "all uninstall removes command-dir links"

# 6c. codex install migrates our symlinks out of the deprecated prompts dir
# (~/.codex/prompts) while preserving foreign entries there.
HOME_CX="$(mktemp -d)"
legacy_prompts="$HOME_CX/.codex/prompts"
mkdir -p "$legacy_prompts"
first_command=""
for d in "$REPO_ROOT"/skills/*/; do
  [[ -f "$d/SKILL.md" ]] || continue
  skill_is_command "$d" || continue
  first_command="$(basename "$d")"
  break
done
[[ -n "$first_command" ]] || fail "no command skill found for codex prompts migration test"
ln -s "$REPO_ROOT/skills/$first_command/SKILL.md" "$legacy_prompts/$first_command.md"
foreign_prompt_src="$(mktemp -d)/foreign-prompt.md"
: > "$foreign_prompt_src"
ln -s "$foreign_prompt_src" "$legacy_prompts/foreign-prompt.md"
HOME="$HOME_CX" "$INSTALL" --target=codex >/dev/null
[[ ! -L "$legacy_prompts/$first_command.md" ]] || fail "deprecated codex prompt for $first_command not migrated"
[[ -L "$legacy_prompts/foreign-prompt.md" ]] || fail "codex prompt cleanup removed a foreign symlink"
pass "codex install cleans the deprecated prompts dir"

# 6b. opencode install migrates our symlinks out of the legacy agent dir
# (~/.config/opencode/agent) while preserving foreign entries there.
HOME_OC="$(mktemp -d)"
legacy_dir="$HOME_OC/.config/opencode/agent"
mkdir -p "$legacy_dir"
first_skill=""
for d in "$REPO_ROOT"/skills/*/; do
  [[ -f "$d/SKILL.md" ]] || continue
  first_skill="$(basename "$d")"
  break
done
[[ -n "$first_skill" ]] || fail "no skill found for legacy migration test"
ln -s "$REPO_ROOT/skills/$first_skill" "$legacy_dir/$first_skill"
foreign_agent_src="$(mktemp -d)/foreign-agent"
mkdir "$foreign_agent_src"
ln -s "$foreign_agent_src" "$legacy_dir/foreign-agent"
HOME="$HOME_OC" "$INSTALL" --target=opencode >/dev/null
[[ ! -L "$legacy_dir/$first_skill" ]] || fail "legacy opencode symlink for $first_skill not migrated"
[[ -L "$legacy_dir/foreign-agent" ]] || fail "legacy cleanup removed a foreign symlink"
got="$(count_links "$HOME_OC/.config/opencode/skills")"
[[ "$got" -eq "$OPENCODE_EXPECTED" ]] || fail "opencode install: expected $OPENCODE_EXPECTED links, got $got"
pass "opencode install links skills/ and cleans the legacy agent dir"

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

# 12. --category links only the matching subset (non-empty, fewer than all).
category_count() {
  # Count skills whose category: frontmatter is in the comma-separated list $1,
  # as installed for target $2 (default claude).
  local want="$1" target="${2:-claude}" n=0
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    skill_is_command "$d" && continue
    skill_is_nested_member "$d" && continue
    skill_matches_target "$d" "$target" || continue
    local cat
    cat="$(grep -m1 '^category:' "$d/SKILL.md" 2>/dev/null | sed 's/^category://')"
    cat="${cat//[[:space:]]/}"
    [[ -n "$cat" ]] && [[ ",$want," == *",$cat,"* ]] && n=$((n + 1))
  done
  echo "$n"
}
ARCH_EXPECTED="$(category_count architecture)"
[[ "$ARCH_EXPECTED" -ge 1 ]] || fail "no architecture skills detected"
[[ "$ARCH_EXPECTED" -lt "$EXPECTED" ]] || fail "architecture subset is not smaller than all"
HOME_CAT="$(mktemp -d)"
HOME="$HOME_CAT" "$INSTALL" --target=claude --category=architecture >/dev/null
got="$(count_links "$HOME_CAT/.claude/skills")"
[[ "$got" -eq "$ARCH_EXPECTED" ]] || fail "category=architecture: expected $ARCH_EXPECTED links, got $got"
pass "category=architecture links only the $ARCH_EXPECTED architecture skills"

# 13. a comma-separated --category list links the union of both subsets.
MULTI_EXPECTED="$(category_count architecture,refactoring)"
HOME_MULTI="$(mktemp -d)"
HOME="$HOME_MULTI" "$INSTALL" --target=claude --category=architecture,refactoring >/dev/null
got="$(count_links "$HOME_MULTI/.claude/skills")"
[[ "$got" -eq "$MULTI_EXPECTED" ]] || fail "category list: expected $MULTI_EXPECTED links, got $got"
pass "category=architecture,refactoring links $MULTI_EXPECTED skills"

# 14. an invalid --category value is rejected.
if HOME="$(mktemp -d)" "$INSTALL" --target=claude --category=bogus >/dev/null 2>&1; then
  fail "invalid --category=bogus was accepted"
fi
pass "invalid --category is rejected"

# 18. a category without a router leaves config.toml alone (communication
#     ships no router, so nothing managed is written to config.toml).
HOME_NOMCP="$(mktemp -d)"
HOME="$HOME_NOMCP" "$INSTALL" --target=codex --category=communication >/dev/null
[[ ! -f "$HOME_NOMCP/.codex/config.toml" ]] \
  || fail "category=communication created config.toml"
pass "category without a router leaves config.toml alone"

# 21. unbalanced markers (hand-deleted end markers) leave the file untouched.
# Drop the managed skill-override end marker so its writer sees an unbalanced
# pair and bails.
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

# 21a. codex install disables every nested router member via [[skills.config]].
#      architecture is routed and has the most members, so it exercises the
#      block best.
HOME_OV="$(mktemp -d)"
HOME="$HOME_OV" "$INSTALL" --target=codex --category=architecture >/dev/null
CONFIG_OV="$HOME_OV/.codex/config.toml"
[[ -f "$CONFIG_OV" ]] || fail "codex install did not create config.toml for overrides"
# Every nested member of the architecture router must be disabled; the router
# itself must not be.
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
  [[ "$(skill_dir_category "$d")" == "architecture" ]] || continue
  name="$(basename "$d")"
  if skill_is_router "$d"; then
    [[ -z "${OV_DISABLED[$name]:-}" ]] || fail "override disabled the router $name"
  elif skill_is_nested_member "$d"; then
    [[ -n "${OV_DISABLED[$name]:-}" ]] || fail "nested member $name not disabled in config.toml"
  fi
done
python3 - "$CONFIG_OV" <<'PY' || fail "override block is not valid TOML"
import sys, tomllib
with open(sys.argv[1], "rb") as f:
    tomllib.load(f)
PY
pass "codex install disables nested router members"

# 21b. a routed category writes only the override block — the installer no
#      longer registers MCP servers at all — and reinstalling is byte-identical.
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

# 21c. uninstall removes the override block but keeps foreign config.
printf '\n[foreign]\nkeep = true\n' >> "$CONFIG_OV2"
HOME="$HOME_OV2" "$INSTALL" --target=codex --category=ai-ml --uninstall >/dev/null
grep -Fxq '[foreign]' "$CONFIG_OV2" || fail "override uninstall dropped foreign config"
grep -q 'skills\.config\|routed-member skill overrides' "$CONFIG_OV2" \
  && fail "override uninstall left our block behind"
pass "override uninstall removes only our block"

# 21d. a config left behind by a version that still registered the
#      knowledge-base MCP servers is cleaned up — by install as well as by
#      uninstall — across every legacy category, foreign tables untouched.
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

# 22. codex install converts plugin subagents to valid custom-agent TOML.
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

# 23. re-running leaves the agent files identical; foreign files survive.
before="$(cat "$AGENTS_DIR/coupling-analyst.toml")"
HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture >/dev/null
[[ "$(cat "$AGENTS_DIR/coupling-analyst.toml")" == "$before" ]] \
  || fail "agent conversion is not idempotent"
printf 'name = "mine"\n' > "$AGENTS_DIR/cohesion-analyst.toml"
HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture >/dev/null 2>&1
grep -Fxq 'name = "mine"' "$AGENTS_DIR/cohesion-analyst.toml" \
  || fail "foreign agent file was overwritten"
pass "agent conversion is idempotent and preserves foreign files"

# 24. uninstall removes generated agents only; foreign files stay.
HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture --uninstall >/dev/null 2>&1
[[ ! -f "$AGENTS_DIR/coupling-analyst.toml" ]] \
  || fail "uninstall left a generated agent file"
[[ -f "$AGENTS_DIR/cohesion-analyst.toml" ]] \
  || fail "uninstall removed a foreign agent file"
pass "uninstall removes only generated agent files"

# 25. a category without agents creates no agents directory.
HOME_NOAG="$(mktemp -d)"
HOME="$HOME_NOAG" "$INSTALL" --target=codex --category=workflow >/dev/null
[[ ! -d "$HOME_NOAG/.codex/agents" ]] \
  || fail "category=workflow created an agents directory"
pass "category without subagents leaves agents directory alone"

# 36. A routed category links only its router at top level; the auto members
#     ride nested under the router's members/ dir (readable, not registered),
#     and none of them leak into the skills directory.
HOME_ROUTED="$(mktemp -d)"
HOME="$HOME_ROUTED" "$INSTALL" --target=claude --category=architecture >/dev/null
ROUTED_SKILLS="$HOME_ROUTED/.claude/skills"
[[ -L "$ROUTED_SKILLS/architecture" ]] || fail "router 'architecture' not linked"
[[ -f "$ROUTED_SKILLS/architecture/SKILL.md" ]] || fail "router SKILL.md not readable"
[[ "$(count_links "$ROUTED_SKILLS")" -eq 1 ]] \
  || fail "routed category linked more than the router at top level"
# A representative member resolves through the router's members/ dir ...
[[ -f "$ROUTED_SKILLS/architecture/members/coupling-cohesion/SKILL.md" ]] \
  || fail "nested member coupling-cohesion not readable via the router"
# ... but is never registered as its own top-level skill.
for member in adr-workflow coupling-cohesion ddd sql-schema-design; do
  [[ ! -e "$ROUTED_SKILLS/$member" ]] \
    || fail "routed member $member leaked into the skills directory"
done
HOME="$HOME_ROUTED" "$INSTALL" --target=claude --category=architecture --uninstall >/dev/null
[[ ! -e "$ROUTED_SKILLS/architecture" ]] || fail "uninstall left the router behind"
pass "routed category registers only its router; members ride nested"

# 36a. Migration from a pre-router install: members used to be linked flat at
#      top level. Those links still resolve, so the dangling-link prune cannot
#      catch them — install must unlink them explicitly, or the members keep
#      registering alongside the router. Foreign entries must survive.
HOME_MIG="$(mktemp -d)"
MIG_SKILLS="$HOME_MIG/.claude/skills"
mkdir -p "$MIG_SKILLS"
mig_members=""
for d in "$REPO_ROOT"/skills/*/; do
  [[ -f "$d/SKILL.md" ]] || continue
  [[ "$(skill_dir_category "$d")" == "architecture" ]] || continue
  skill_is_nested_member "$d" || continue
  name="$(basename "$d")"
  ln -s "$REPO_ROOT/skills/$name" "$MIG_SKILLS/$name"
  mig_members+="$name"$'\n'
done
[[ -n "$mig_members" ]] || fail "no nested architecture members found for the migration test"
mig_foreign="$(mktemp -d)/foreign"
mkdir "$mig_foreign"
ln -s "$mig_foreign" "$MIG_SKILLS/foreign-skill"
HOME="$HOME_MIG" "$INSTALL" --target=claude --category=architecture >/dev/null
while IFS= read -r name; do
  [[ -n "$name" ]] || continue
  [[ ! -e "$MIG_SKILLS/$name" ]] \
    || fail "pre-router flat link for $name survived the upgrade"
done <<< "$mig_members"
[[ -L "$MIG_SKILLS/architecture" ]] || fail "migration did not link the router"
[[ -L "$MIG_SKILLS/foreign-skill" ]] || fail "migration removed a foreign symlink"
# ... and --uninstall clears the flat links too, not just the router.
HOME="$HOME_MIG" "$INSTALL" --target=claude --category=architecture >/dev/null
while IFS= read -r name; do
  [[ -n "$name" ]] || continue
  ln -s "$REPO_ROOT/skills/$name" "$MIG_SKILLS/$name"
done <<< "$mig_members"
HOME="$HOME_MIG" "$INSTALL" --target=claude --category=architecture --uninstall >/dev/null
while IFS= read -r name; do
  [[ -n "$name" ]] || continue
  [[ ! -e "$MIG_SKILLS/$name" ]] || fail "uninstall left the pre-router flat link for $name"
done <<< "$mig_members"
[[ -L "$MIG_SKILLS/foreign-skill" ]] || fail "uninstall removed a foreign symlink"
pass "pre-router flat member links are cleaned up on install and uninstall"

# 37. A `targets:` skill installs only for the agents it lists. No shipped skill
#     currently uses the field, so exercise it with a temporary fixture skill
#     that opts out of claude: it must reach codex and opencode only — and a
#     stale link in the claude skills dir is cleaned up by the next install.
TGT_FIXTURE="$REPO_ROOT/skills/zz-targets-fixture"
rm_tgt_fixture() { rm -rf "$TGT_FIXTURE"; }
trap rm_tgt_fixture EXIT
mkdir -p "$TGT_FIXTURE/scripts"
cat >"$TGT_FIXTURE/SKILL.md" <<'FIXTURE'
---
name: zz-targets-fixture
description: Temporary fixture used by test_install.sh to exercise the targets field.
category: communication
targets: codex, opencode
---

# Fixture
FIXTURE
: >"$TGT_FIXTURE/scripts/bundled.txt"
HOME_TGT="$(mktemp -d)"
mkdir -p "$HOME_TGT/.claude/skills"
ln -s "$TGT_FIXTURE" "$HOME_TGT/.claude/skills/zz-targets-fixture"
HOME="$HOME_TGT" "$INSTALL" --target=all --category=communication >/dev/null
[[ ! -e "$HOME_TGT/.claude/skills/zz-targets-fixture" ]] \
  || fail "targets: fixture installed for claude"
[[ -f "$HOME_TGT/.codex/skills/zz-targets-fixture/scripts/bundled.txt" ]] \
  || fail "targets: fixture missing (or incomplete) under codex"
[[ -f "$HOME_TGT/.config/opencode/skills/zz-targets-fixture/scripts/bundled.txt" ]] \
  || fail "targets: fixture missing (or incomplete) under opencode"
# Its category-mates are unaffected and keep their bundled files.
[[ -f "$HOME_TGT/.claude/skills/documentation/SKILL.md" ]] \
  || fail "documentation not installed as a whole directory for claude"
rm_tgt_fixture
trap - EXIT
pass "targets: skips excluded agents and prunes a stale link"

# 38. A dangling symlink left by a skill the repo no longer ships is pruned;
#     foreign and still-valid links are left alone.
HOME_STALE="$(mktemp -d)"
HOME="$HOME_STALE" "$INSTALL" --target=claude --category=communication >/dev/null
STALE_SKILLS="$HOME_STALE/.claude/skills"
ln -s "$REPO_ROOT/skills/removed-skill" "$STALE_SKILLS/removed-skill"
foreign_dangling="$(mktemp -d)/gone"
ln -s "$foreign_dangling" "$STALE_SKILLS/foreign-dangling"
HOME="$HOME_STALE" "$INSTALL" --target=claude --category=communication >/dev/null
[[ ! -L "$STALE_SKILLS/removed-skill" ]] || fail "stale link for a removed skill survived"
[[ -L "$STALE_SKILLS/foreign-dangling" ]] || fail "prune removed a foreign dangling symlink"
[[ -L "$STALE_SKILLS/documentation" ]] || fail "prune removed a valid skill link"
pass "install prunes dangling links to skills the repo dropped"

# 39. --instructions composes instructions/ into each agent's global file,
#     inside the managed markers only. Without the flag nothing is written.
HOME_INS="$(mktemp -d)"
mkdir -p "$HOME_INS/.claude" "$HOME_INS/.codex"
printf 'my own notes\n\n@RTK.md\n' >"$HOME_INS/.claude/CLAUDE.md"
cp "$HOME_INS/.claude/CLAUDE.md" "$HOME_INS/claude-before.md"
HOME="$HOME_INS" "$INSTALL" --target=claude --category=communication >/dev/null
diff -q "$HOME_INS/claude-before.md" "$HOME_INS/.claude/CLAUDE.md" >/dev/null \
  || fail "instructions written without --instructions"
pass "instructions are not touched without --instructions"

# 40. With the flag the block lands, hand-written content survives, and a
#     second run is a no-op (idempotent).
HOME="$HOME_INS" "$INSTALL" --target=claude --category=communication --instructions >/dev/null
CLAUDE_MD="$HOME_INS/.claude/CLAUDE.md"
grep -q '^my own notes$' "$CLAUDE_MD" || fail "hand-written line lost"
grep -q '^@RTK.md$' "$CLAUDE_MD" || fail "@-import lost"
grep -q 'agents instructions (managed by install.sh' "$CLAUDE_MD" || fail "begin marker missing"
grep -q '<!-- <<< agents instructions <<< -->' "$CLAUDE_MD" || fail "end marker missing"
grep -q 'Use uv for Python package development' "$CLAUDE_MD" || fail "fragment body missing"
cp "$CLAUDE_MD" "$HOME_INS/claude-once.md"
HOME="$HOME_INS" "$INSTALL" --target=claude --category=communication --instructions >/dev/null
diff -q "$HOME_INS/claude-once.md" "$CLAUDE_MD" >/dev/null \
  || fail "second --instructions run changed the file"
pass "instructions block installs once and is idempotent"

# 41. --uninstall strips only our block, restoring the file byte for byte.
HOME="$HOME_INS" "$INSTALL" --target=claude --category=communication --instructions --uninstall >/dev/null
diff -q "$HOME_INS/claude-before.md" "$CLAUDE_MD" >/dev/null \
  || fail "uninstall did not restore the original instruction file"
pass "instructions uninstall removes only the managed block"

# 42. codex gets its own file created from nothing; opencode deliberately gets
#     none (it already reads ~/.claude/CLAUDE.md).
HOME_INS2="$(mktemp -d)"
HOME="$HOME_INS2" "$INSTALL" --target=all --category=communication --instructions >/dev/null
[[ -f "$HOME_INS2/.codex/AGENTS.md" ]] || fail "codex AGENTS.md was not created"
grep -q 'Use uv for Python package development' "$HOME_INS2/.codex/AGENTS.md" \
  || fail "codex AGENTS.md has no fragment body"
[[ ! -e "$HOME_INS2/.config/opencode/AGENTS.md" ]] \
  || fail "opencode instruction file written (would duplicate ~/.claude/CLAUDE.md)"
pass "instructions create codex's file and skip opencode on purpose"

# 43. Unbalanced markers (a hand edit) leave the file completely alone, and
#     --dry-run never writes.
HOME_INS3="$(mktemp -d)"
mkdir -p "$HOME_INS3/.claude"
printf 'notes\n\n<!-- >>> agents instructions (managed by install.sh, do not edit) >>> -->\nstray\n' \
  >"$HOME_INS3/.claude/CLAUDE.md"
cp "$HOME_INS3/.claude/CLAUDE.md" "$HOME_INS3/unbalanced-before.md"
HOME="$HOME_INS3" "$INSTALL" --target=claude --category=communication --instructions >/dev/null 2>&1
diff -q "$HOME_INS3/unbalanced-before.md" "$HOME_INS3/.claude/CLAUDE.md" >/dev/null \
  || fail "unbalanced markers did not protect the file"
HOME_INS4="$(mktemp -d)"
HOME="$HOME_INS4" "$INSTALL" --target=codex --category=communication --instructions --dry-run >/dev/null
[[ ! -e "$HOME_INS4/.codex/AGENTS.md" ]] || fail "dry-run wrote an instruction file"
pass "unbalanced markers and dry-run never write instruction files"

echo "all install.sh tests passed"
