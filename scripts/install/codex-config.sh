# shellcheck shell=bash
# Sourced by install.sh. Codex config.toml blocks: legacy MCP cleanup and routed-member overrides.

# --- Legacy Codex MCP cleanup ----------------------------------------------
#
# Earlier versions registered each plugin's knowledge-base MCP server in
# ~/.codex/config.toml between marker comments, backed by a runtime venv at a
# fixed path. Those servers are gone — the skills' references/ pages are read
# directly now — so both install and uninstall strip whatever a previous
# version left behind. Install has to do it too: an upgrade would otherwise
# keep Codex pointing at a server script this repo no longer ships.

codex_config_path() { printf '%s/.codex/config.toml' "$HOME"; }

# Categories that ever shipped an .mcp.json. Hardcoded, because the files this
# list was once derived from no longer exist.
LEGACY_MCP_CATEGORIES="architecture refactoring"

codex_mcp_runtime_dir() { printf '%s/.codex/agents-mcp-runtime' "$HOME"; }

mcp_begin_marker() {
  printf '# >>> agents:%s MCP servers (managed by install.sh, do not edit) >>>' "$1"
}

mcp_end_marker() {
  printf '# <<< agents:%s MCP servers <<<' "$1"
}

# Drop every managed MCP block a previous version wrote, plus the runtime venv
# it provisioned. Foreign [mcp_servers.*] tables live outside our markers and
# are never touched.
remove_legacy_codex_mcp() {
  local config cat
  config="$(codex_config_path)"
  for cat in $LEGACY_MCP_CATEGORIES; do
    managed_block_remove "$config" "$(mcp_begin_marker "$cat")" \
      "$(mcp_end_marker "$cat")" "legacy $cat MCP servers"
  done

  local venv
  venv="$(codex_mcp_runtime_dir)"
  if [[ -d "$venv" ]]; then
    check_record codex legacy-mcp-runtime "$venv" stale
    if ((DRY_RUN)); then
      printf '[dry-run] remove %s\n' "$venv"
    else
      rm -rf "$venv"
      printf '  removed   legacy MCP runtime venv %s\n' "$venv"
    fi
  fi
}

# --- Codex routed-member skill overrides -----------------------------------
#
# Codex discovers skills by scanning its skill roots recursively and following
# symlinks (openai/codex#22275), so the sub-skills nested under a router's
# members/ dir get registered as independent skills — defeating the router's
# progressive disclosure. (Claude registers only top-level skills, so it is
# unaffected.) To keep the members hidden under codex, disable each nested
# member in ~/.codex/config.toml via a [[skills.config]] entry (enabled =
# false), which drops it from the model's skill list. The entry selects the
# member by `path`, the only selector the Codex config reference documents.
# Codex canonicalizes both sides, so the repo path matches the member it
# discovers through the router's symlinks, and a foreign skill that happens to
# share the member's name stays enabled. The block is marker-delimited so
# install and uninstall stay idempotent and never touch config we do not own.

skill_override_begin_marker() {
  printf '# >>> agents routed-member skill overrides (managed by install.sh, do not edit) >>>'
}

skill_override_end_marker() {
  printf '# <<< agents routed-member skill overrides <<<'
}

# Render one [[skills.config]] disable table per member name read on stdin,
# selecting the member by the path of its SKILL.md in this repo.
render_skill_override_toml() {
  local name first=1 root
  # The clone path lands in a TOML basic string, so escape \ and ".
  root="${REPO_ROOT//\\/\\\\}"
  root="${root//\"/\\\"}"
  while IFS= read -r name; do
    [[ -n "$name" ]] || continue
    if [[ ! "$name" =~ ^[A-Za-z0-9_-]+$ ]]; then
      printf '  WARN      skill name %q is not a bare identifier (skipping override)\n' \
        "$name" >&2
      continue
    fi
    ((first)) || printf '\n'
    first=0
    printf '[[skills.config]]\npath = "%s/skills/%s/SKILL.md"\nenabled = false\n' \
      "$root" "$name"
  done
}

# Strip our override block from ~/.codex/config.toml (leaving foreign config).
remove_codex_member_overrides() {
  managed_block_remove "$(codex_config_path)" "$(skill_override_begin_marker)" \
    "$(skill_override_end_marker)" "routed-member skill overrides"
}

# Print the nested members (one per line) of every router Codex sees under
# dest_dir: one linked by this run (named in the newline-separated `skills`)
# or one whose link a previous run left in place. Deriving the set from the
# installed routers rather than from the --category filter keeps a narrower
# re-run from re-enabling the members of routers it did not touch (#562).
codex_routed_members() {
  local dest_dir="$1" skills="$2" d router member
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    [[ "$(skill_activation "$d/SKILL.md")" == "router" ]] || continue
    router="$(basename "$d")"
    if ! { [[ $'\n'"$skills"$'\n' == *$'\n'"$router"$'\n'* ]] &&
      skill_matches_target "$d/SKILL.md" codex; } &&
      [[ "$(readlink "$dest_dir/$router" 2>/dev/null)" != "$REPO_ROOT/skills/$router" ]]; then
      continue
    fi
    for member in "$d"members/*; do
      [[ -e "$member" ]] && printf '%s\n' "$(basename "$member")"
    done
  done
}

# Write the managed override block that disables the nested router members
# named on stdin (one per line). With no names, any stale block is removed.
# Uses only shell built-ins and the same core tools as the rest of install.sh
# (no sort/wc/tr) so it works under the minimal sandboxed PATH.
install_codex_member_overrides() {
  local members="" count=0 name toml
  while IFS= read -r name; do
    [[ -n "${name//[[:space:]]/}" ]] || continue
    members+="$name"$'\n'
    count=$((count + 1))
  done
  toml="$(printf '%s' "$members" | render_skill_override_toml)"
  if [[ -z "$toml" ]]; then
    remove_codex_member_overrides
    return 0
  fi
  managed_block_set "$(codex_config_path)" "$(skill_override_begin_marker)" \
    "$(skill_override_end_marker)" "$toml" "$count routed members disabled"
}
