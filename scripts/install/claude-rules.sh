# shellcheck shell=bash
# Sourced by install.sh. Path-scoped Claude rules and the uv-init context hook.

# --- Path-scoped Claude rules ------------------------------------------------
#
# A fragment with `paths:` (comma-separated globs) goes to Claude as its own
# ~/.claude/rules/agents-<fragment>.md with `paths:` frontmatter, so it enters
# context only when Claude reads a matching file. The globs are written as a
# quoted YAML list: a bare `**/*.R` would parse as a YAML alias, and Claude
# loads a rule whose frontmatter does not parse unconditionally. The
# `managed-by:` line (ignored by Claude) marks the files this script owns;
# rules without it are never touched.

claude_rules_dir() { printf '%s/.claude/rules' "$HOME"; }

claude_rule_marker() { printf 'managed-by: fabiandistler/agents install.sh'; }

claude_rule_dest() {
  local name="${1##*/}"
  printf '%s/agents-%s' "$(claude_rules_dir)" "$name"
}

render_claude_rule() {
  local file="$1" paths glob globs
  paths="$(instruction_field "$file" paths)"
  printf -- '---\npaths:\n'
  # read -a, not an unquoted for-loop: the globs must not expand against $PWD.
  IFS=',' read -ra globs <<<"$paths"
  for glob in "${globs[@]}"; do
    glob="${glob#"${glob%%[![:space:]]*}"}"
    glob="${glob%"${glob##*[![:space:]]}"}"
    [[ -n "$glob" ]] && printf '  - "%s"\n' "$glob"
  done
  printf '%s\n---\n\n' "$(claude_rule_marker)"
  fragment_body "$file"
}

# Our rule files currently on disk, one path per line.
list_managed_claude_rules() {
  local file
  for file in "$(claude_rules_dir)"/agents-*.md; do
    [[ -f "$file" ]] || continue
    grep -qxF "$(claude_rule_marker)" "$file" && printf '%s\n' "$file"
  done
}

remove_claude_rule() {
  if ((DRY_RUN)); then
    check_record claude claude-rule "$1" stale
    printf '[dry-run] remove %s\n' "$1"
    return 0
  fi
  rm "$1"
  printf '  removed   %s\n' "$1"
}

# Write every path-scoped fragment as a rule file and drop managed rule files
# whose fragment is gone or lost its `paths:`. A foreign file already at a
# destination is left alone with a warning.
install_claude_rules() {
  local file dest content wanted=""
  for file in "$(instructions_dir)"/*.md; do
    [[ -f "$file" ]] || continue
    fragment_matches_target "$file" claude || continue
    fragment_is_claude_rule "$file" claude || continue
    dest="$(claude_rule_dest "$file")"
    wanted+="$dest"$'\n'
    content="$(render_claude_rule "$file")"
    owned_file_set "$dest" rule <<<"$content"
  done
  while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    grep -qxF "$file" <<<"$wanted" || remove_claude_rule "$file"
  done < <(list_managed_claude_rules)
}

remove_claude_rules() {
  local file
  while IFS= read -r file; do
    [[ -n "$file" ]] && remove_claude_rule "$file"
  done < <(list_managed_claude_rules)
}

# Strip our instructions block from a target's file, leaving the rest.
remove_instructions() {
  local target="$1" dest
  dest="$(instruction_file_for "$target")" || return 1
  managed_block_remove "$dest" "$(instructions_begin_marker)" \
    "$(instructions_end_marker)" "instructions block"
}

python_init_hook_command() {
  printf 'python3 "%s/.agents/instructions/python_init_context.py" --baseline "%s/.agents/instructions/30-python.md"' \
    "$HOME" "$HOME"
}

# Print ~/.claude/settings.json with the Python uv-init context hook installed.
# Exit 1 when the file is unreadable/invalid or has an incompatible hooks shape.
claude_settings_with_python_hook() {
  python3 - "$REPO_ROOT/scripts" "$1" "$2" <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from python_init_context import with_claude_hook

path = Path(sys.argv[2])
try:
    settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
except (OSError, ValueError):
    sys.exit(1)
if not isinstance(settings, dict):
    sys.exit(1)
try:
    wanted = with_claude_hook(settings, sys.argv[3])
except (TypeError, ValueError):
    sys.exit(1)
print(json.dumps(wanted, indent=2))
PY
}

# Print ~/.claude/settings.json without our Python hook. Exit 10 when absent.
claude_settings_without_python_hook() {
  python3 - "$REPO_ROOT/scripts" "$1" <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from python_init_context import without_claude_hook

path = Path(sys.argv[2])
try:
    settings = json.loads(path.read_text(encoding="utf-8"))
except (OSError, ValueError):
    sys.exit(1)
if not isinstance(settings, dict):
    sys.exit(1)
wanted = without_claude_hook(settings)
if wanted == settings:
    sys.exit(10)
print(json.dumps(wanted, indent=2))
PY
}

install_claude_python_hook() {
  local file="$HOME/.claude/settings.json" command content before="" existed=0
  if ! instruction_payload_available 30-python.md ||
    ! instruction_payload_available python_init_context.py; then
    printf '  WARN      cannot install the Claude uv-init context hook because an instruction payload is unavailable\n' >&2
    return 0
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    printf '  WARN      python3 not found; cannot install the Claude uv-init context hook\n' >&2
    return 0
  fi
  if [[ -L "$file" ]]; then
    check_record claude python-init-hook "$file" foreign
    ((CHECK_MODE)) || printf '  WARN      %s is a symlink, leaving it untouched (Python uv-init context hook)\n' \
      "$file" >&2
    return 0
  fi
  if [[ -f "$file" ]]; then
    before="$(cat "$file")"
    existed=1
  fi
  command="$(python_init_hook_command)"
  if ! content="$(claude_settings_with_python_hook "$file" "$command")"; then
    check_record claude python-init-hook "$file" foreign
    ((CHECK_MODE)) || printf '  WARN      %s is not a compatible JSON object, leaving it untouched (Python uv-init context hook)\n' \
      "$file" >&2
    return 0
  fi
  if [[ -f "$file" && "$(cat "$file")" == "$content" ]]; then
    printf '  ok        %s (Python uv-init context hook)\n' "$file"
    return 0
  fi
  if [[ -f "$file" ]]; then
    check_record claude python-init-hook "$file" stale
  else
    check_record claude python-init-hook "$file" missing
  fi
  if ((DRY_RUN)); then
    printf '[dry-run] write %s\n' "$file"
    return 0
  fi
  ensure_parent "${file%/*}"
  if ((UPDATE_MODE)); then
    if ((existed)); then
      if [[ ! -f "$file" || -L "$file" || "$(cat "$file")" != "$before" ]]; then
        printf '  WARN      %s changed during --update; leaving it untouched\n' "$file" >&2
        return 0
      fi
    elif [[ -e "$file" || -L "$file" ]]; then
      printf '  WARN      %s appeared during --update; leaving it untouched\n' "$file" >&2
      return 0
    fi
  fi
  write_file_atomic "$file" "$content"
  printf '  updated   %s (Python uv-init context hook)\n' "$file"
}

remove_claude_python_hook() {
  local file="$HOME/.claude/settings.json" content status=0
  [[ -f "$file" ]] && grep -qF python_init_context.py "$file" || return 0
  if [[ -L "$file" ]]; then
    printf '  WARN      %s is a symlink, leaving it untouched (Python uv-init context hook)\n' \
      "$file" >&2
    return 0
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    printf '  WARN      python3 not found; remove the Python uv-init context hook from %s by hand\n' \
      "$file" >&2
    return 0
  fi
  content="$(claude_settings_without_python_hook "$file")" || status=$?
  case "$status" in
    0) ;;
    10) return 0 ;;
    *)
      printf '  WARN      %s is not a JSON object, leaving it untouched (Python uv-init context hook)\n' \
        "$file" >&2
      return 0
      ;;
  esac
  if ((DRY_RUN)); then
    printf '[dry-run] remove %s\n' "$file"
    return 0
  fi
  write_file_atomic "$file" "$content"
  printf '  removed   Python uv-init context hook from %s\n' "$file"
}
