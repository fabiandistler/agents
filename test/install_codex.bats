#!/usr/bin/env bats
# install.sh for codex: the config.toml blocks (routed-member overrides,
# legacy MCP cleanup) and the plugin subagents.

load install_helper

setup() {
  install_setup
}

# Print the managed config.toml blocks in file order.
block_order() {
  awk '
    /^# >>> agents routed-member skill overrides/ { print "routed" }
    /^# >>> agents PR merge guard/ { print "merge" }
  ' "$1"
}

# A codex config and runtime venv left by a version that still registered
# the knowledge-base MCP servers, next to a foreign server.
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
    >"$home/.codex/config.toml"
  mkdir -p "$home/.codex/agents-mcp-runtime/bin"
  : >"$home/.codex/agents-mcp-runtime/bin/python"
}

assert_legacy_mcp_gone() {
  local config="$1" what="$2"
  grep -Fxq '[mcp_servers.foreign]' "$config" ||
    fail "$what dropped a foreign MCP server"
  grep -Fxq 'command = "keep-me"' "$config" ||
    fail "$what dropped the foreign server's body"
  if grep -q 'MCP servers\|mcp_servers\.\(architecture\|refactoring\)-kb' "$config"; then
    fail "$what left a legacy managed MCP block behind"
  fi
}

@test "category without a router leaves config.toml alone" {
  # a category without a router leaves config.toml alone (communication
  # ships no router, so nothing managed is written to config.toml).
  HOME_NOMCP="$(mktemp -d)"
  HOME="$HOME_NOMCP" "$INSTALL" --target=codex --category=communication >/dev/null
  [[ ! -f "$HOME_NOMCP/.codex/config.toml" ]] ||
    fail "category=communication created config.toml"
}

@test "unbalanced markers leave config.toml untouched" {
  # unbalanced markers (hand-deleted end markers) leave the file untouched.
  # Drop the managed skill-override end marker so its writer sees an unbalanced
  # pair and bails.
  HOME_UNBAL="$(mktemp -d)"
  HOME="$HOME_UNBAL" "$INSTALL" --target=codex --category=architecture >/dev/null
  CONFIG_UNBAL="$HOME_UNBAL/.codex/config.toml"
  grep -vE '^# <<< agents' "$CONFIG_UNBAL" >"$CONFIG_UNBAL.tmp"
  printf '\n[precious]\nkeep = true\n' >>"$CONFIG_UNBAL.tmp"
  mv "$CONFIG_UNBAL.tmp" "$CONFIG_UNBAL"
  before="$(cat "$CONFIG_UNBAL")"
  HOME="$HOME_UNBAL" "$INSTALL" --target=codex --category=architecture >/dev/null 2>&1
  [[ "$(cat "$CONFIG_UNBAL")" == "$before" ]] ||
    fail "install modified a config with unbalanced markers"
  HOME="$HOME_UNBAL" "$INSTALL" --target=codex --category=architecture --uninstall >/dev/null 2>&1
  [[ "$(cat "$CONFIG_UNBAL")" == "$before" ]] ||
    fail "uninstall modified a config with unbalanced markers"
}

@test "codex install disables nested router members" {
  # codex install disables every nested router member via [[skills.config]].
  # architecture is routed and has the most members, so it exercises the
  # block best.
  HOME_OV="$(mktemp -d)"
  HOME="$HOME_OV" "$INSTALL" --target=codex --category=architecture >/dev/null
  CONFIG_OV="$HOME_OV/.codex/config.toml"
  [[ -f "$CONFIG_OV" ]] || fail "codex install did not create config.toml for overrides"
  # Every nested member of the architecture router must be disabled; the router
  # itself must not be. Members are selected by the documented `path` selector
  # (#565): the SKILL.md of the member in this repo, never by `name`.
  ov_members="$(
    "$PYTHON" - "$CONFIG_OV" "$REPO_ROOT" <<'PY'
import sys, tomllib
from pathlib import Path
with open(sys.argv[1], "rb") as f:
    cfg = tomllib.load(f)
skills_dir = Path(sys.argv[2]) / "skills"
for entry in cfg.get("skills", {}).get("config", []):
    if "name" in entry:
        sys.exit(f"override uses the name selector: {entry}")
    path = Path(entry["path"])
    if entry.get("enabled") is not False or not path.is_file():
        sys.exit(f"override does not disable an existing SKILL.md: {entry}")
    if path.name != "SKILL.md" or path.parent.parent != skills_dir:
        sys.exit(f"override path is not a skill in this repo: {entry}")
    print(path.parent.name)
PY
  )" || fail "override block is malformed"
  declare -A OV_DISABLED=()
  while IFS= read -r name; do
    [[ -n "$name" ]] && OV_DISABLED["$name"]=1
  done <<<"$ov_members"
  [[ "${#OV_DISABLED[@]}" -ge 1 ]] || fail "override block selects no member by path"
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
  "$PYTHON" - "$CONFIG_OV" <<'PY' || fail "override block is not valid TOML"
import sys, tomllib
with open(sys.argv[1], "rb") as f:
    tomllib.load(f)
PY
}

@test "override-only config is written and idempotent" {
  # a routed category writes only the override block — the installer no
  # longer registers MCP servers at all — and reinstalling is byte-identical.
  HOME_OV2="$(mktemp -d)"
  HOME="$HOME_OV2" "$INSTALL" --target=codex --category=ai-ml >/dev/null
  CONFIG_OV2="$HOME_OV2/.codex/config.toml"
  [[ -f "$CONFIG_OV2" ]] || fail "routed category=ai-ml created no config.toml"
  ! grep -q '^\[mcp_servers\.' "$CONFIG_OV2" ||
    fail "install wrote mcp_servers into config.toml"
  before="$(cat "$CONFIG_OV2")"
  HOME="$HOME_OV2" "$INSTALL" --target=codex --category=ai-ml >/dev/null
  [[ "$(cat "$CONFIG_OV2")" == "$before" ]] || fail "override registration is not idempotent"
}

@test "override uninstall removes only our block" {
  # uninstall removes the override block but keeps foreign config.
  HOME_OV2="$(mktemp -d)"
  HOME="$HOME_OV2" "$INSTALL" --target=codex --category=ai-ml >/dev/null
  CONFIG_OV2="$HOME_OV2/.codex/config.toml"
  printf '\n[foreign]\nkeep = true\n' >>"$CONFIG_OV2"
  HOME="$HOME_OV2" "$INSTALL" --target=codex --category=ai-ml --uninstall >/dev/null
  grep -Fxq '[foreign]' "$CONFIG_OV2" || fail "override uninstall dropped foreign config"
  ! grep -q 'skills\.config\|routed-member skill overrides' "$CONFIG_OV2" ||
    fail "override uninstall left our block behind"
}

@test "unchanged override block is neither rewritten nor planned for removal" {
  # an unchanged override block is left alone: a reinstall reports "ok"
  # without rewriting the file, and a dry-run plans no removal.
  HOME_OV3="$(mktemp -d)"
  HOME="$HOME_OV3" "$INSTALL" --target=codex --category=ai-ml >/dev/null
  CONFIG_OV3="$HOME_OV3/.codex/config.toml"
  inode_before="$(file_inode "$CONFIG_OV3")"
  ov_output="$(HOME="$HOME_OV3" "$INSTALL" --target=codex --category=ai-ml 2>&1)"
  [[ "$(file_inode "$CONFIG_OV3")" == "$inode_before" ]] ||
    fail "reinstall rewrote an unchanged override block"
  grep -q '^  ok .*config.toml' <<<"$ov_output" ||
    fail "reinstall did not report the unchanged override block as ok"
  ov_dry="$(HOME="$HOME_OV3" "$INSTALL" --target=codex --category=ai-ml --dry-run 2>&1)"
  ! grep -Fq "[dry-run] remove $CONFIG_OV3" <<<"$ov_dry" ||
    fail "dry-run planned removing an override block it would keep"
}

@test "managed blocks retain their content, inode, and order" {
  # routed-member and guard blocks retain their order and inode on rerun.
  HOME_BLOCK_ORDER="$(mktemp -d)"
  HOME="$HOME_BLOCK_ORDER" "$INSTALL" --target=codex --category=architecture --merge-guard >/dev/null
  CONFIG_BLOCK_ORDER="$HOME_BLOCK_ORDER/.codex/config.toml"
  expected_block_order=$'routed\nmerge'
  [[ "$(block_order "$CONFIG_BLOCK_ORDER")" == "$expected_block_order" ]] ||
    fail "managed blocks were written in the wrong order"
  block_content_before="$(cat "$CONFIG_BLOCK_ORDER")"
  block_inode_before="$(file_inode "$CONFIG_BLOCK_ORDER")"
  HOME="$HOME_BLOCK_ORDER" "$INSTALL" --target=codex --category=architecture --merge-guard >/dev/null
  [[ "$(cat "$CONFIG_BLOCK_ORDER")" == "$block_content_before" ]] ||
    fail "reinstall changed managed block content or order"
  [[ "$(file_inode "$CONFIG_BLOCK_ORDER")" == "$block_inode_before" ]] ||
    fail "reinstall rewrote unchanged managed blocks"
  [[ "$(block_order "$CONFIG_BLOCK_ORDER")" == "$expected_block_order" ]] ||
    fail "reinstall changed managed block order"
}

@test "narrower --category re-run keeps overrides of installed routers" {
  # a narrower --category re-run keeps the overrides of routers still
  # installed (#562): the full install links the architecture and ai-ml
  # routers, a communication-only re-run leaves those links in place, so
  # their nested members must stay disabled.
  HOME_OV4="$(mktemp -d)"
  HOME="$HOME_OV4" "$INSTALL" --target=codex >/dev/null
  CONFIG_OV4="$HOME_OV4/.codex/config.toml"
  before="$(cat "$CONFIG_OV4")"
  grep -q 'routed-member skill overrides' <<<"$before" ||
    fail "full codex install wrote no override block"
  HOME="$HOME_OV4" "$INSTALL" --target=codex --category=communication >/dev/null
  [[ "$(cat "$CONFIG_OV4")" == "$before" ]] ||
    fail "narrower --category re-run changed the override block of installed routers"
}

@test "routed-member and merge-guard blocks keep their order and inode" {
  # Reinstalling routed-member and merge-guard blocks leaves their order
  # and config inode unchanged.
  HOME_OV5="$(mktemp -d)"
  HOME="$HOME_OV5" "$INSTALL" --target=codex --category=ai-ml --merge-guard >/dev/null
  CONFIG_OV5="$HOME_OV5/.codex/config.toml"
  before="$(cat "$CONFIG_OV5")"
  inode_before="$(stat -c %i "$CONFIG_OV5")"
  reinstall_output="$(HOME="$HOME_OV5" "$INSTALL" --target=codex --category=ai-ml --merge-guard 2>&1)"
  [[ "$(cat "$CONFIG_OV5")" == "$before" ]] ||
    fail "reinstall changed the routed-member/merge-guard block order"
  [[ "$(stat -c %i "$CONFIG_OV5")" == "$inode_before" ]] ||
    fail "reinstall rewrote an unchanged routed-member/merge-guard config"
  grep -q '^  ok .*routed members disabled' <<<"$reinstall_output" ||
    fail "reinstall did not report the unchanged routed-member block as ok"
  grep -q '^  ok .*PR merge guard hook' <<<"$reinstall_output" ||
    fail "reinstall did not report the unchanged merge-guard block as ok"
}

@test "install strips legacy MCP blocks and the runtime venv" {
  # a config left behind by a version that still registered the
  # knowledge-base MCP servers is cleaned up — by install as well as by
  # uninstall — across every legacy category, foreign tables untouched.
  # Install path: cleanup runs even for a category that never shipped a server.
  HOME_LEGACY="$(mktemp -d)"
  make_legacy_mcp_home "$HOME_LEGACY"
  CONFIG_LEGACY="$HOME_LEGACY/.codex/config.toml"
  HOME="$HOME_LEGACY" "$INSTALL" --target=codex --category=ai-ml >/dev/null
  assert_legacy_mcp_gone "$CONFIG_LEGACY" "install"
  [[ ! -d "$HOME_LEGACY/.codex/agents-mcp-runtime" ]] ||
    fail "install left the legacy MCP runtime venv behind"
  "$PYTHON" - "$CONFIG_LEGACY" <<'PY' || fail "legacy cleanup left invalid TOML"
import sys, tomllib
with open(sys.argv[1], "rb") as f:
    tomllib.load(f)
PY
  before="$(cat "$CONFIG_LEGACY")"
  HOME="$HOME_LEGACY" "$INSTALL" --target=codex --category=ai-ml >/dev/null
  [[ "$(cat "$CONFIG_LEGACY")" == "$before" ]] || fail "legacy cleanup is not idempotent"
}

@test "uninstall strips legacy MCP blocks; dry-run only reports them" {
  # Uninstall path: same cleanup, and a dry-run changes nothing.
  HOME_LEGACY_UN="$(mktemp -d)"
  make_legacy_mcp_home "$HOME_LEGACY_UN"
  CONFIG_LEGACY_UN="$HOME_LEGACY_UN/.codex/config.toml"
  before="$(cat "$CONFIG_LEGACY_UN")"
  dry_output="$(HOME="$HOME_LEGACY_UN" "$INSTALL" --target=codex --dry-run 2>&1)"
  [[ "$(cat "$CONFIG_LEGACY_UN")" == "$before" ]] ||
    fail "dry-run modified the legacy config"
  [[ -d "$HOME_LEGACY_UN/.codex/agents-mcp-runtime" ]] ||
    fail "dry-run removed the legacy runtime venv"
  grep -Fq "[dry-run] remove $CONFIG_LEGACY_UN" <<<"$dry_output" ||
    fail "dry-run did not plan legacy block removal"
  grep -Fq "[dry-run] remove $HOME_LEGACY_UN/.codex/agents-mcp-runtime" <<<"$dry_output" ||
    fail "dry-run did not plan legacy venv removal"
  HOME="$HOME_LEGACY_UN" "$INSTALL" --target=codex --uninstall >/dev/null
  assert_legacy_mcp_gone "$CONFIG_LEGACY_UN" "uninstall"
  [[ ! -d "$HOME_LEGACY_UN/.codex/agents-mcp-runtime" ]] ||
    fail "uninstall left the legacy MCP runtime venv behind"
}

@test "codex install converts subagents to valid agent TOML" {
  # codex install converts plugin subagents to valid custom-agent TOML.
  HOME_AG="$(mktemp -d)"
  HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture >/dev/null
  AGENTS_DIR="$HOME_AG/.codex/agents"
  for agent in coupling-analyst cohesion-analyst; do
    [[ -f "$AGENTS_DIR/$agent.toml" ]] || fail "missing $agent.toml"
  done
  "$PYTHON" - "$AGENTS_DIR" <<'PY' || fail "agent TOML is invalid or incomplete"
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
}

@test "agent conversion is idempotent and preserves foreign files" {
  # re-running leaves the agent files identical; foreign files survive.
  HOME_AG="$(mktemp -d)"
  HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture >/dev/null
  AGENTS_DIR="$HOME_AG/.codex/agents"
  before="$(cat "$AGENTS_DIR/coupling-analyst.toml")"
  agent_inode_before="$(file_inode "$AGENTS_DIR/coupling-analyst.toml")"
  HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture >/dev/null
  [[ "$(cat "$AGENTS_DIR/coupling-analyst.toml")" == "$before" ]] ||
    fail "agent conversion is not idempotent"
  [[ "$(file_inode "$AGENTS_DIR/coupling-analyst.toml")" == "$agent_inode_before" ]] ||
    fail "reinstall rewrote an unchanged agent TOML"
  printf 'name = "mine"\n' >"$AGENTS_DIR/cohesion-analyst.toml"
  HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture >/dev/null 2>&1
  grep -Fxq 'name = "mine"' "$AGENTS_DIR/cohesion-analyst.toml" ||
    fail "foreign agent file was overwritten"
}

@test "uninstall removes only generated agent files" {
  # uninstall removes generated agents only; foreign files stay.
  HOME_AG="$(mktemp -d)"
  HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture >/dev/null
  AGENTS_DIR="$HOME_AG/.codex/agents"
  printf 'name = "mine"\n' >"$AGENTS_DIR/cohesion-analyst.toml"
  HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture --uninstall >/dev/null 2>&1
  [[ ! -f "$AGENTS_DIR/coupling-analyst.toml" ]] ||
    fail "uninstall left a generated agent file"
  [[ -f "$AGENTS_DIR/cohesion-analyst.toml" ]] ||
    fail "uninstall removed a foreign agent file"
}

@test "category without subagents leaves agents directory alone" {
  # a category without agents creates no agents directory.
  HOME_NOAG="$(mktemp -d)"
  HOME="$HOME_NOAG" "$INSTALL" --target=codex --category=workflow >/dev/null
  [[ ! -d "$HOME_NOAG/.codex/agents" ]] ||
    fail "category=workflow created an agents directory"
}

@test "stale generated agent files are pruned, foreign and live ones kept" {
  # a generated agent whose source is gone (renamed or deleted subagent) is
  # pruned on the next codex run, whatever --category says; foreign files
  # and generated agents whose source still exists stay.
  HOME_PRUNE="$(mktemp -d)"
  HOME="$HOME_PRUNE" "$INSTALL" --target=codex --category=architecture >/dev/null
  PRUNE_DIR="$HOME_PRUNE/.codex/agents"
  sed 's/coupling-analyst/retired-analyst/' "$PRUNE_DIR/coupling-analyst.toml" \
    >"$PRUNE_DIR/retired-analyst.toml"
  printf 'name = "hand-written"\n' >"$PRUNE_DIR/hand-written.toml"
  HOME="$HOME_PRUNE" "$INSTALL" --target=codex --category=workflow --dry-run >/dev/null
  [[ -f "$PRUNE_DIR/retired-analyst.toml" ]] || fail "dry-run pruned a stale agent file"
  HOME="$HOME_PRUNE" "$INSTALL" --target=codex --category=workflow >/dev/null
  [[ ! -e "$PRUNE_DIR/retired-analyst.toml" ]] ||
    fail "generated agent without a source was not pruned"
  [[ -f "$PRUNE_DIR/hand-written.toml" ]] || fail "prune removed a foreign agent file"
  [[ -f "$PRUNE_DIR/coupling-analyst.toml" ]] ||
    fail "prune removed an agent whose source still exists"
}
