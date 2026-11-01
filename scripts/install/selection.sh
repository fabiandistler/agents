# shellcheck shell=bash
# Sourced by install.sh. --check rows, target directories, and the bash frontmatter readers that pick skills.

check_kind_for_what() {
  case "$1" in
    *routed*member*) printf 'routed-member-overrides' ;;
    *"instruction payload"*) printf 'instruction-payload' ;;
    *"instruction"*) printf 'instructions' ;;
    *"Claude rule"*) printf 'claude-rule' ;;
    *"OpenCode agent"*) printf 'opencode-agent' ;;
    *"agent "*) printf 'codex-agent' ;;
    *"PR merge guard"*) printf 'merge-guard' ;;
    *"secret read guard"*) printf 'secret-guard' ;;
    *"legacy"*) printf 'legacy-managed-file' ;;
    *) printf 'managed-file' ;;
  esac
}

check_tsv_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//$'\t'/\\t}"
  value="${value//$'\n'/\\n}"
  printf '%s' "$value"
}

check_record() {
  ((CHECK_MODE)) || return 0
  local target="${1:-$CHECK_CURRENT_TARGET}" kind="$2" path="$3" state="$4" row
  local escaped_target escaped_kind escaped_path escaped_state
  [[ -n "$target" ]] || target="$TARGET"
  escaped_target="$(check_tsv_escape "$target")"
  escaped_kind="$(check_tsv_escape "$kind")"
  escaped_path="$(check_tsv_escape "$path")"
  escaped_state="$(check_tsv_escape "$state")"
  printf -v row '%s\t%s\t%s\t%s' \
    "$escaped_target" "$escaped_kind" "$escaped_path" "$escaped_state"
  [[ $'\n'"$CHECK_ROWS" == *$'\n'"$row"$'\n'* ]] || CHECK_ROWS+="$row"$'\n'
}

target_dir_for() {
  case "$1" in
    claude) printf '%s/.claude/skills\n' "$HOME" ;;
    codex) printf '%s/.agents/skills\n' "$HOME" ;;
    opencode) printf '%s/.config/opencode/skills\n' "$HOME" ;;
    *)
      echo "unknown target: $1" >&2
      return 1
      ;;
  esac
}

# Where Claude's earlier symlink installer placed its command skills.
target_command_dir_for() {
  case "$1" in
    claude) printf '%s/.claude/commands\n' "$HOME" ;;
    *)
      echo "unknown target: $1" >&2
      return 1
      ;;
  esac
}

opencode_legacy_command_dir() { printf '%s/.config/opencode/command\n' "$HOME"; }

resolve_targets() {
  if [[ -n "$RESOLVED_TARGETS" ]]; then
    local resolved_target
    while IFS= read -r resolved_target; do
      if [[ -n "$resolved_target" ]]; then
        printf '%s\n' "$resolved_target"
      fi
    done <<<"$RESOLVED_TARGETS"
    return 0
  fi
  if [[ "$TARGET" == "all" ]]; then
    printf 'claude\ncodex\nopencode\n'
  else
    printf '%s\n' "$TARGET"
  fi
}

# Read the comma-separated `environments:` frontmatter value of a SKILL.md.
# Prints the raw value (may be empty if the field is absent).
skill_environments() {
  local skill_md="$1" line
  line="$(grep -m1 '^environments:' "$skill_md" 2>/dev/null || true)"
  printf '%s' "${line#environments:}"
}

# True if a skill belongs to the requested environment. A skill with no
# `environments:` field belongs to every environment.
skill_matches_env() {
  local skill_md="$1" want="$2" envs
  [[ "$want" == "all" ]] && return 0
  envs="$(skill_environments "$skill_md")"
  [[ -z "${envs//[[:space:]]/}" ]] && return 0
  local IFS=','
  for e in $envs; do
    e="${e//[[:space:]]/}"
    [[ "$e" == "$want" ]] && return 0
  done
  return 1
}

# Read the comma-separated `targets:` frontmatter value of a SKILL.md.
# Prints the raw value (may be empty if the field is absent).
skill_targets() {
  local skill_md="$1" line
  line="$(grep -m1 '^targets:' "$skill_md" 2>/dev/null || true)"
  printf '%s' "${line#targets:}"
}

# True if a skill should be installed for the given target. A skill with no
# `targets:` field belongs to every target.
skill_matches_target() {
  local skill_md="$1" want="$2" targets
  targets="$(skill_targets "$skill_md")"
  [[ -z "${targets//[[:space:]]/}" ]] && return 0
  local IFS=','
  for t in $targets; do
    t="${t//[[:space:]]/}"
    [[ "$t" == "$want" ]] && return 0
  done
  return 1
}

# Read the `activation:` frontmatter value of a SKILL.md. Prints `command`
# for user-invoked skills, `router` for a per-category router skill, `auto`
# otherwise (the default when absent).
skill_activation() {
  local skill_md="$1" line act
  line="$(grep -m1 '^activation:' "$skill_md" 2>/dev/null || true)"
  act="${line#activation:}"
  act="${act//[[:space:]]/}"
  case "$act" in
    command) printf 'command' ;;
    router) printf 'router' ;;
    *) printf 'auto' ;;
  esac
}

# Print the `category:` frontmatter value of a SKILL.md (empty if absent).
skill_category() {
  local skill_md="$1" line cat
  line="$(grep -m1 '^category:' "$skill_md" 2>/dev/null || true)"
  cat="${line#category:}"
  printf '%s' "${cat//[[:space:]]/}"
}

# Space-padded list of categories that ship a router skill (activation:
# router). A routed category's auto skills are nested under the router's
# members/ dir, so install.sh links only the router and skips the members.
routed_categories() {
  local out=" "
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    if [[ "$(skill_activation "$d/SKILL.md")" == "router" ]]; then
      out+="$(skill_category "$d/SKILL.md") "
    fi
  done
  printf '%s' "$out"
}

# True if a skill's `category:` frontmatter matches the requested filter.
# `all` matches everything; a skill without the field only matches `all`.
skill_matches_category() {
  local skill_md="$1" want="$2" line cat
  [[ "$want" == "all" ]] && return 0
  line="$(grep -m1 '^category:' "$skill_md" 2>/dev/null || true)"
  cat="${line#category:}"
  cat="${cat//[[:space:]]/}"
  [[ -n "$cat" ]] || return 1
  [[ ",${want// /}," == *",$cat,"* ]]
}

list_skills() {
  # A directory under skills/ is a skill iff it contains SKILL.md.
  for d in "$REPO_ROOT"/skills/*/; do
    local name
    name="$(basename "$d")"
    [[ -f "$d/SKILL.md" ]] || continue
    skill_matches_env "$d/SKILL.md" "$ENV" || continue
    skill_matches_category "$d/SKILL.md" "$CATEGORY" || continue
    printf '%s\n' "$name"
  done
}
