# shellcheck shell=bash
# Sourced by install.sh. Saved install state: read, write, and plan --uninstall's change to it.

install_state_file() {
  local state_home="${XDG_STATE_HOME:-$HOME/.local/state}"
  printf '%s/fabiandistler-agents/install.json' "${state_home%/}"
}

# Reads the saved install state into the SAVED_* globals. Returns 4 without a
# message when no state file exists, so each caller words that case itself.
read_install_state() {
  local file reader_pid status
  file="$(install_state_file)"
  if [[ -L "$file" ]] || { [[ -e "$file" ]] && [[ ! -f "$file" ]]; }; then
    printf 'saved install state is not a regular file: %s\n' "$file" >&2
    return 1
  fi
  [[ -f "$file" ]] || return 4
  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required to read --update state" >&2
    return 1
  fi
  exec 3< <(
    python3 - "$file" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as state_file:
        state = json.load(state_file)
    targets = state["targets"]
    environment = state["env"]
    category = state["category"]
    instructions = state["instructions"]
    merge_guard = state["merge_guard"]
    secret_guard = state["secret_guard"]
    repo_root = state["repo_root"]
    if (
        not isinstance(targets, list)
        or not targets
        or any(target not in {"claude", "codex", "opencode"} for target in targets)
        or len(set(targets)) != len(targets)
        or not isinstance(environment, str)
        or "\0" in environment
        or not isinstance(category, str)
        or "\0" in category
        or type(instructions) is not bool
        or type(merge_guard) is not bool
        or type(secret_guard) is not bool
        or not isinstance(repo_root, str)
        or not repo_root.startswith("/")
        or "\0" in repo_root
    ):
        raise ValueError("invalid fields")
    values = [
        ",".join(targets),
        environment,
        category,
        "1" if instructions else "0",
        "1" if merge_guard else "0",
        "1" if secret_guard else "0",
        repo_root,
    ]
    sys.stdout.buffer.write("\0".join(values).encode("utf-8") + b"\0")
except (OSError, UnicodeError, ValueError, KeyError, TypeError):
    sys.stderr.write("saved install state is invalid\n")
    sys.exit(1)
PY
  )
  reader_pid=$!
  if ! IFS= read -r -d '' SAVED_TARGETS_CSV <&3 ||
    ! IFS= read -r -d '' SAVED_ENV <&3 ||
    ! IFS= read -r -d '' SAVED_CATEGORY <&3 ||
    ! IFS= read -r -d '' SAVED_INSTRUCTIONS <&3 ||
    ! IFS= read -r -d '' SAVED_MERGE <&3 ||
    ! IFS= read -r -d '' SAVED_SECRET <&3 ||
    ! IFS= read -r -d '' SAVED_REPO_ROOT <&3; then
    exec 3<&-
    wait "$reader_pid" || true
    echo "saved install state is invalid" >&2
    return 1
  fi
  exec 3<&-
  if wait "$reader_pid"; then
    :
  else
    status=$?
    return "$status"
  fi
}

load_install_state() {
  local status target
  if read_install_state; then
    :
  else
    status=$?
    if ((status == 4)); then
      printf 'no saved install state at %s; install once with --target=claude|codex|opencode|all before --update\n' \
        "$(install_state_file)" >&2
    fi
    return "$status"
  fi

  ENV="$SAVED_ENV"
  CATEGORY="$SAVED_CATEGORY"
  INSTRUCTIONS="$SAVED_INSTRUCTIONS"
  GUARDS=""
  [[ "$SAVED_MERGE" == 1 ]] && GUARDS+=" merge"
  [[ "$SAVED_SECRET" == 1 ]] && GUARDS+=" secret"
  # shellcheck disable=SC2034  # the checkout-move rebasing in the other parts reads it
  OLD_REPO_ROOT="$SAVED_REPO_ROOT"
  RESOLVED_TARGETS=""
  IFS=',' read -ra _resolved_targets <<<"$SAVED_TARGETS_CSV"
  for target in "${_resolved_targets[@]}"; do
    RESOLVED_TARGETS+="$target"$'\n'
  done
  # shellcheck disable=SC2034  # options.sh and resolve_targets (selection.sh) read TARGET
  if [[ "$SAVED_TARGETS_CSV" == "claude,codex,opencode" ]]; then
    TARGET=all
  elif [[ "$SAVED_TARGETS_CSV" == *','* ]]; then
    TARGET=resolved
  else
    TARGET="$SAVED_TARGETS_CSV"
  fi
  [[ "$ENV" == all ]] || FILTER_FLAGS+=" --env"
  [[ "$CATEGORY" == all ]] || FILTER_FLAGS+=" --category"
}

json_quote() {
  local value="$1" escaped="" character escaped_character code index
  for ((index = 0; index < ${#value}; index++)); do
    character="${value:index:1}"
    case "$character" in
      '"') escaped+='\\"' ;;
      \\) escaped+='\\\\' ;;
      $'\b') escaped+='\\b' ;;
      $'\f') escaped+='\\f' ;;
      $'\n') escaped+='\\n' ;;
      $'\r') escaped+='\\r' ;;
      $'\t') escaped+='\\t' ;;
      *)
        printf -v code '%d' "'$character"
        if ((code < 32)); then
          printf -v escaped_character '\\u%04x' "$code"
          escaped+="$escaped_character"
        else
          escaped+="$character"
        fi
        ;;
    esac
  done
  printf '"%s"' "$escaped"
}

# Arguments: comma-separated targets, env, category, instructions, merge guard,
# secret guard (each 0 or 1), and repo root.
write_install_state() {
  local targets_csv="$1" env="$2" category="$3" instructions="$4" merge_guard="$5" \
    secret_guard="$6" repo_root="$7"
  local file dir target targets_json="[" separator="" content tmp before="" had_file=0
  IFS=',' read -ra _state_targets <<<"$targets_csv"
  for target in "${_state_targets[@]}"; do
    [[ -n "$target" ]] || continue
    targets_json+="$separator$(json_quote "$target")"
    separator=,
  done
  targets_json+="]"
  file="$(install_state_file)"
  dir="${file%/*}"
  if [[ -L "$file" ]] || { [[ -e "$file" ]] && [[ ! -f "$file" ]]; }; then
    printf 'refusing to replace non-regular install state path: %s\n' "$file" >&2
    return 1
  fi
  if [[ -f "$file" ]]; then
    before="$(cat "$file")"
    had_file=1
  fi
  ensure_parent "$dir"
  content="{\"targets\":$targets_json,\"env\":$(json_quote "$env"),\"category\":$(json_quote "$category"),\"instructions\":$( ((instructions)) && printf true || printf false),\"merge_guard\":$( ((merge_guard)) && printf true || printf false),\"secret_guard\":$( ((secret_guard)) && printf true || printf false),\"repo_root\":$(json_quote "$repo_root") }"
  tmp="$file.tmp.$$"
  if [[ -e "$tmp" || -L "$tmp" ]]; then
    printf 'refusing to replace temporary install state path: %s\n' "$tmp" >&2
    return 1
  fi
  printf '%s\n' "$content" >"$tmp"
  if ((had_file)); then
    if [[ ! -f "$file" || -L "$file" || "$(cat "$file")" != "$before" ]]; then
      rm "$tmp"
      printf 'install state changed during this run; leaving it untouched: %s\n' "$file" >&2
      return 1
    fi
  elif [[ -e "$file" || -L "$file" ]]; then
    rm "$tmp"
    printf 'install state appeared during this run; leaving it untouched: %s\n' "$file" >&2
    return 1
  fi
  mv "$tmp" "$file"
}

detect_targets() {
  local targets=""
  if command -v claude >/dev/null 2>&1 || [[ -d "$HOME/.claude" ]]; then
    targets=claude
  fi
  if command -v codex >/dev/null 2>&1 || [[ -d "$HOME/.codex" ]]; then
    [[ -z "$targets" ]] || targets+=$'\n'
    targets+=codex
  fi
  if command -v opencode >/dev/null 2>&1 || [[ -d "$HOME/.config/opencode" ]]; then
    [[ -z "$targets" ]] || targets+=$'\n'
    targets+=opencode
  fi
  printf '%s\n' "$targets"
}

# Prints the categories a --category value selects, one per line, in the order
# of $CATEGORIES.
category_names() {
  local value="${1//[[:space:]]/}" name
  for name in $CATEGORIES; do
    if [[ "$value" == all || ",$value," == *",$name,"* ]]; then
      printf '%s\n' "$name"
    fi
  done
}

# Decides, before anything is removed, what --uninstall does to the saved
# state: keep it (nothing saved was removed), delete it (the whole saved
# selection was removed), rewrite it without the removed targets or categories,
# or keep it with a note when one selection cannot express the result (a
# category or env removed from only some saved targets).
plan_uninstall_state() {
  local status target name removed_targets kept_targets="" kept_categories="" \
    removed_categories touched_target=0 touched_category=0 all_targets_removed=1
  UNINSTALL_STATE_ACTION=keep
  if read_install_state; then
    :
  else
    status=$?
    ((status == 4)) && return 0
    return "$status"
  fi
  UNINSTALL_STATE_BEFORE="$(cat "$(install_state_file)")"
  removed_targets=" $(resolve_targets | tr '\n' ' ')"
  IFS=',' read -ra _saved_targets <<<"$SAVED_TARGETS_CSV"
  for target in "${_saved_targets[@]}"; do
    if [[ "$removed_targets" == *" $target "* ]]; then
      touched_target=1
    else
      kept_targets+="${kept_targets:+,}$target"
      all_targets_removed=0
    fi
  done
  removed_categories=" $(category_names "$CATEGORY" | tr '\n' ' ')"
  while IFS= read -r name; do
    if [[ "$removed_categories" == *" $name "* ]]; then
      touched_category=1
    else
      kept_categories+="${kept_categories:+,}$name"
    fi
  done < <(category_names "$SAVED_CATEGORY")
  ((touched_target && touched_category)) || return 0

  if [[ "$ENV" != all && "$ENV" != "$SAVED_ENV" ]]; then
    UNINSTALL_STATE_ACTION=partial
  elif ((all_targets_removed)); then
    if [[ -z "$kept_categories" ]]; then
      UNINSTALL_STATE_ACTION=delete
    else
      UNINSTALL_STATE_ACTION=rewrite
      UNINSTALL_STATE_TARGETS="$SAVED_TARGETS_CSV"
      UNINSTALL_STATE_CATEGORY="$kept_categories"
      UNINSTALL_STATE_INSTRUCTIONS=$((SAVED_INSTRUCTIONS && ! INSTRUCTIONS))
      UNINSTALL_STATE_MERGE="$SAVED_MERGE"
      [[ "$GUARDS" != *' merge'* ]] || UNINSTALL_STATE_MERGE=0
      UNINSTALL_STATE_SECRET="$SAVED_SECRET"
      [[ "$GUARDS" != *' secret'* ]] || UNINSTALL_STATE_SECRET=0
    fi
  elif [[ -z "$kept_categories" ]]; then
    UNINSTALL_STATE_ACTION=rewrite
    UNINSTALL_STATE_TARGETS="$kept_targets"
    UNINSTALL_STATE_CATEGORY="$SAVED_CATEGORY"
    UNINSTALL_STATE_INSTRUCTIONS="$SAVED_INSTRUCTIONS"
    UNINSTALL_STATE_MERGE="$SAVED_MERGE"
    UNINSTALL_STATE_SECRET="$SAVED_SECRET"
  else
    UNINSTALL_STATE_ACTION=partial
  fi
}

apply_uninstall_state() {
  local file
  file="$(install_state_file)"
  case "$UNINSTALL_STATE_ACTION" in
    keep) return 0 ;;
    partial)
      printf 'install state keeps the saved selection: it cannot record removing a category or env from only some saved targets, so --update reinstalls it (%s)\n' \
        "$file" >&2
      return 0
      ;;
  esac
  if ((DRY_RUN)); then
    printf '  would %s install state %s\n' "$UNINSTALL_STATE_ACTION" "$file"
    return 0
  fi
  if [[ ! -f "$file" || -L "$file" || "$(cat "$file")" != "$UNINSTALL_STATE_BEFORE" ]]; then
    printf 'install state changed during this run; leaving it untouched: %s\n' "$file" >&2
    return 1
  fi
  if [[ "$UNINSTALL_STATE_ACTION" == delete ]]; then
    rm "$file"
    printf '  removed   %s (install state)\n' "$file"
  else
    write_install_state "$UNINSTALL_STATE_TARGETS" "$SAVED_ENV" "$UNINSTALL_STATE_CATEGORY" \
      "$UNINSTALL_STATE_INSTRUCTIONS" "$UNINSTALL_STATE_MERGE" "$UNINSTALL_STATE_SECRET" \
      "$SAVED_REPO_ROOT"
    printf '  updated   %s (install state)\n' "$file"
  fi
}
