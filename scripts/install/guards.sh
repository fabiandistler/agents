# shellcheck shell=bash
# Sourced by install.sh. Pre-tool guards: the PR merge guard and the secret read guard.

# --- Pre-tool guards (PR merge guard, secret read guard) ----------------------
#
# Agents act under the user's GitHub account, so branch rules cannot stop them
# from merging; a pre-tool hook can. The decision and the hook entry both live
# in scripts/pr_merge_guard.py; this section only places the entry in each
# agent's user-level config. Claude gets the guard from the merge-guard plugin
# instead, which this section installs with the claude CLI; earlier versions
# wrote it into ~/.claude/settings.json, and the Claude migration below removes
# that entry. settings.json is JSON and cannot carry marker comments, so our
# entry is identified by the script name in its command, and only that entry is
# ever removed.
#
# The secret read guard (scripts/secret_read_guard.py) is installed the same
# way: it keeps credential files and environment dumps out of the agent's
# context. Claude gets it from the secret-guard plugin.

# A guard is named by its key (merge, secret); the script, plugin and opencode
# adapter names derive from it.
guard_script() {
  case "$1" in
    merge) printf 'pr_merge_guard' ;;
    secret) printf 'secret_read_guard' ;;
  esac
}

guard_label() {
  case "$1" in
    merge) printf 'PR merge guard' ;;
    secret) printf 'secret read guard' ;;
  esac
}

guard_plugin() { printf '%s-guard@fabiandistler-agents' "$1"; }

guard_opencode_file() {
  local script
  script="$(guard_script "$1")"
  printf '%s.js' "${script//_/-}"
}

guard_command() {
  printf 'python3 "%s/scripts/%s.py" --harness %s' "$REPO_ROOT" "$(guard_script "$1")" "$2"
}

render_codex_guard_toml() {
  local guard="$1" command
  command="$(guard_command "$guard" codex)"
  python3 - "$REPO_ROOT/scripts" "$(guard_script "$guard")" "$command" <<'PY'
import importlib
import sys

sys.path.insert(0, sys.argv[1])
from pr_merge_guard import codex_hook_toml

guard = importlib.import_module(sys.argv[2])
print(codex_hook_toml(sys.argv[3], guard.HOOK_MATCHER, guard.HOOK_STATUS))
PY
}

codex_guard_trust_findings() {
  local config="$1"
  python3 - "$config" <<'PY'
import ast
import hashlib
import json
import os
import re
import sys

try:
    import tomllib
except ImportError:
    tomllib = None

def toml_scalar(value):
    value = value.strip()
    if value in ("true", "false"):
        return value == "true"
    if re.fullmatch(r"[0-9]+", value):
        return int(value)
    if value.startswith(('"', "'")):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value[1:-1]
    return value

def minimal_toml(text):
    config = {"hooks": {"PreToolUse": [], "state": {}}}
    section = ""
    group = None
    handler = None
    nested_state = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[[hooks.PreToolUse]]":
            group = {"hooks": []}
            config["hooks"]["PreToolUse"].append(group)
            section, handler, nested_state = "group", None, None
            continue
        if line == "[[hooks.PreToolUse.hooks]]":
            if group is None:
                continue
            handler = {}
            group["hooks"].append(handler)
            section, nested_state = "handler", None
            continue
        if line == "[hooks.state]":
            section, group, handler, nested_state = "state", None, None, None
            continue
        if line.startswith("[hooks.state.") and line.endswith("]"):
            key_text = line[len("[hooks.state."):-1]
            nested_state = toml_scalar(key_text)
            config["hooks"]["state"].setdefault(nested_state, {})
            section, group, handler = "nested-state", None, None
            continue
        if line.startswith("[") or "=" not in line:
            section, group, handler, nested_state = "", None, None, None
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if section == "group" and group is not None:
            group[key] = toml_scalar(value)
        elif section == "handler" and handler is not None:
            handler[key] = toml_scalar(value)
        elif section == "state":
            state_key = toml_scalar(key)
            state_entry = {}
            for field in ("trusted_hash", "enabled"):
                match = re.search(rf"\b{field}\s*=\s*([^,}}]+)", value)
                if match:
                    state_entry[field] = toml_scalar(match.group(1))
            config["hooks"]["state"][state_key] = state_entry
        elif section == "nested-state" and nested_state is not None:
            config["hooks"]["state"].setdefault(nested_state, {})[key] = toml_scalar(value)
    return config

try:
    config_path = os.path.abspath(sys.argv[1])
    with open(config_path, "rb") as config_file:
        if tomllib is not None:
            config = tomllib.load(config_file)
        else:
            config = minimal_toml(config_file.read().decode("utf-8"))
except (OSError, UnicodeError, ValueError):
    sys.exit(3)

hooks = config.get("hooks", {})
groups = hooks.get("PreToolUse", []) if isinstance(hooks, dict) else []
state = hooks.get("state", {}) if isinstance(hooks, dict) else {}
if not isinstance(groups, list) or not isinstance(state, dict):
    sys.exit(3)

for guard, filename in (("merge", "pr_merge_guard.py"), ("secret", "secret_read_guard.py")):
    matches = []
    for group_index, group in enumerate(groups):
        if not isinstance(group, dict):
            continue
        handlers = group.get("hooks", [])
        if not isinstance(handlers, list):
            continue
        for handler_index, handler in enumerate(handlers):
            if not isinstance(handler, dict):
                continue
            command = handler.get("command")
            if isinstance(command, str) and filename in command:
                matches.append((group_index, handler_index, group, handler))
    if len(matches) > 1:
        print(f"{guard}\tduplicate")
        continue
    if not matches:
        continue

    group_index, handler_index, group, handler = matches[0]
    normalized = {
        "type": "command",
        "command": handler["command"],
        "timeout": handler.get("timeout", 600),
        "async": handler.get("async", False),
    }
    for field in ("commandWindows", "statusMessage", "additionalContextLimit"):
        if handler.get(field) is not None:
            normalized[field] = handler[field]
    identity = {
        "event_name": "pre_tool_use",
        "matcher": group.get("matcher"),
        "hooks": [normalized],
    }
    current_hash = "sha256:" + hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    keys = (
        f"{config_path}:pre_tool_use:{group_index}:{handler_index}",
        f"{os.path.realpath(config_path)}:pre_tool_use:{group_index}:{handler_index}",
    )
    saved = next((state.get(key) for key in keys if key in state), None)
    if not isinstance(saved, dict) or saved.get("enabled") is False or saved.get("trusted_hash") != current_hash:
        print(f"{guard}\tuntrusted-hook")
PY
}

check_codex_guard_hooks() {
  local config guard begin end marker_count expected actual result status kind
  config="$(codex_config_path)"
  [[ -f "$config" ]] || return 0
  for guard in merge secret; do
    begin="$(guard_begin_marker "$guard")"
    end="$(guard_end_marker "$guard")"
    marker_count="$(grep -Fxc "$begin" "$config" || true)"
    ((marker_count > 0)) || continue
    kind="$(check_kind_for_what "$(guard_label "$guard")")"
    if ! block_markers_balanced "$begin" "$end" <"$config"; then
      check_record codex "$kind" "$config" foreign
      continue
    fi
    if ((marker_count > 1)); then
      check_record codex "$kind" "$config" duplicate
      continue
    fi
    if ! expected="$(render_codex_guard_toml "$guard")"; then
      check_record codex "$kind" "$config" foreign
      continue
    fi
    actual="$(awk -v b="$begin" -v e="$end" '
      $0 == b { inside = 1; next }
      $0 == e { inside = 0; exit }
      inside { if (printed) printf "\n"; printf "%s", $0; printed = 1 }
    ' "$config")"
    [[ "$actual" == "$expected" ]] || check_record codex "$kind" "$config" stale
    result=""
    status=0
    result="$(codex_guard_trust_findings "$config")" || status=$?
    case "$status" in
      0)
        while IFS=$'\t' read -r found_guard state; do
          [[ "$found_guard" == "$guard" ]] || continue
          check_record codex "$kind" "$config" "$state"
        done <<<"$result"
        ;;
      2) check_record codex "$kind" "$config" untrusted-hook ;;
      *) check_record codex "$kind" "$config" foreign ;;
    esac
  done
}

guard_begin_marker() {
  printf '# >>> agents %s (managed by install.sh, do not edit) >>>' "$(guard_label "$1")"
}

guard_end_marker() { printf '# <<< agents %s <<<' "$(guard_label "$1")"; }

opencode_guard_link() {
  printf '%s/.config/opencode/plugins/%s' "$HOME" "$(guard_opencode_file "$1")"
}

MARKETPLACE="fabiandistler/agents"

# Print ~/.claude/settings.json without the guard entry. Exit 10: nothing to
# change; exit 1: not a JSON object.
claude_settings_without_merge_guard() {
  python3 - "$REPO_ROOT/scripts" "$1" <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from pr_merge_guard import without_claude_hook

path = Path(sys.argv[2])
try:
    settings = json.loads(path.read_text(encoding="utf-8"))
except ValueError:
    sys.exit(1)
if not isinstance(settings, dict):
    sys.exit(1)
wanted = without_claude_hook(settings)
if wanted == settings:
    sys.exit(10)
print(json.dumps(wanted, indent=2))
PY
}

# Drop the guard entry an earlier version wrote into ~/.claude/settings.json.
remove_claude_settings_merge_guard() {
  local file="$HOME/.claude/settings.json" content status=0 before
  [[ -f "$file" ]] && grep -qF pr_merge_guard.py "$file" || return 0
  if ! command -v python3 >/dev/null 2>&1; then
    printf '  WARN      python3 not found; remove the pr_merge_guard.py hook from %s by hand\n' \
      "$file" >&2
    return 0
  fi
  before="$(cat "$file")"
  content="$(claude_settings_without_merge_guard "$file")" || status=$?
  case "$status" in
    0) ;;
    10) return 0 ;;
    *)
      printf '  WARN      %s is not a JSON object, leaving it untouched (PR merge guard)\n' \
        "$file" >&2
      return 0
      ;;
  esac
  if ((DRY_RUN)); then
    check_record claude merge-guard "$file" stale
    printf '[dry-run] remove %s\n' "$file"
    return 0
  fi
  if ((UPDATE_MODE)) &&
    { [[ ! -f "$file" ]] || [[ -L "$file" ]] || [[ "$(cat "$file")" != "$before" ]] ||
      ! grep -qF pr_merge_guard.py "$file"; }; then
    printf '  WARN      %s changed during --update; leaving it untouched\n' "$file" >&2
    return 0
  fi
  write_file_atomic "$file" "$content"
  printf '  removed   PR merge guard hook from %s (now the merge-guard plugin)\n' "$file"
}

# The guard plugin's state in Claude Code's user scope: enabled, disabled or
# absent. A project-scope install does not count: it covers one project only.
claude_plugin_state() {
  local listing
  listing="$(claude plugin list --json)" || return 1
  python3 - "$1" "$listing" <<'PY'
import json
import sys

plugin, listing = sys.argv[1:]
for entry in json.loads(listing):
    if entry["id"] == plugin and entry["scope"] == "user":
        print({True: "enabled", False: "disabled"}[entry["enabled"]])
        break
else:
    print("absent")
PY
}

# The names of the plugin marketplaces Claude Code knows, one per line.
claude_marketplace_names() {
  local listing
  listing="$(claude plugin marketplace list --json)" || return 1
  python3 - "$listing" <<'PY'
import json
import sys

for marketplace in json.loads(sys.argv[1]):
    print(marketplace["name"])
PY
}

# Install the guard plugin with the claude CLI, after adding the marketplace if
# Claude does not know it under any source yet. A plugin the user disabled
# stays disabled: claude plugin install would turn it back on without asking.
install_claude_guard_plugin() {
  local guard="$1" label plugin marketplace kind state marketplaces
  label="$(guard_label "$guard")"
  plugin="$(guard_plugin "$guard")"
  marketplace="${plugin#*@}"
  kind="$(check_kind_for_what "$label")"
  if ! command -v claude >/dev/null 2>&1; then
    check_record claude "$kind" "$plugin" missing
    printf '  WARN      claude CLI not found; install the %s with: claude plugin install %s\n' \
      "$label" "$plugin" >&2
    return 0
  fi
  state="$(claude_plugin_state "$plugin")"
  case "$state" in
    enabled)
      printf '  ok        %s (%s plugin)\n' "$plugin" "$label"
      return 0
      ;;
    disabled)
      check_record claude "$kind" "$plugin" missing
      printf '  WARN      %s is disabled in Claude Code; turn it on with: claude plugin enable %s\n' \
        "$plugin" "$plugin" >&2
      return 0
      ;;
  esac
  check_record claude "$kind" "$plugin" missing
  marketplaces="$(claude_marketplace_names)"
  if ! grep -Fxq "$marketplace" <<<"$marketplaces"; then
    if ((DRY_RUN)); then
      printf '[dry-run] claude plugin marketplace add %s\n' "$MARKETPLACE"
    else
      claude plugin marketplace add "$MARKETPLACE" >/dev/null
      printf '  added     %s marketplace from %s\n' "$marketplace" "$MARKETPLACE"
    fi
  fi
  if ((DRY_RUN)); then
    printf '[dry-run] claude plugin install %s\n' "$plugin"
    return 0
  fi
  claude plugin install "$plugin" >/dev/null
  printf '  installed %s (%s plugin)\n' "$plugin" "$label"
}

# Remove the guard plugin with the claude CLI if Claude has it in user scope.
uninstall_claude_guard_plugin() {
  local guard="$1" label plugin tool state
  label="$(guard_label "$guard")"
  plugin="$(guard_plugin "$guard")"
  for tool in claude python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      printf '  WARN      %s not found; remove the %s with: claude plugin uninstall %s\n' \
        "$tool" "$label" "$plugin" >&2
      return 0
    fi
  done
  state="$(claude_plugin_state "$plugin")"
  [[ "$state" != absent ]] || return 0
  if ((DRY_RUN)); then
    printf '[dry-run] claude plugin uninstall %s\n' "$plugin"
    return 0
  fi
  claude plugin uninstall "$plugin" >/dev/null
  printf '  removed   %s (%s plugin)\n' "$plugin" "$label"
}

install_guard() {
  local guard="$1" target="$2" label toml
  label="$(guard_label "$guard")"
  if ! command -v python3 >/dev/null 2>&1; then
    printf '  WARN      python3 not found; the %s needs it (skipping %s)\n' \
      "$label" "$target" >&2
    return 0
  fi
  case "$target" in
    claude) install_claude_guard_plugin "$guard" ;;
    codex)
      if ! toml="$(render_codex_guard_toml "$guard")"; then
        printf '  WARN      cannot render the Codex %s hook (skipping)\n' "$label" >&2
        return 0
      fi
      managed_block_set "$(codex_config_path)" "$(guard_begin_marker "$guard")" \
        "$(guard_end_marker "$guard")" "$toml" "$label hook"
      ;;
    opencode)
      ensure_parent "${HOME}/.config/opencode/plugins"
      link_one "$REPO_ROOT/scripts/opencode/$(guard_opencode_file "$guard")" \
        "$(opencode_guard_link "$guard")"
      ;;
  esac
}

uninstall_guard() {
  local guard="$1"
  case "$2" in
    claude) uninstall_claude_guard_plugin "$guard" ;;
    codex)
      managed_block_remove "$(codex_config_path)" "$(guard_begin_marker "$guard")" \
        "$(guard_end_marker "$guard")" "$(guard_label "$guard") hook"
      ;;
    opencode)
      unlink_one "$REPO_ROOT/scripts/opencode/$(guard_opencode_file "$guard")" \
        "$(opencode_guard_link "$guard")"
      ;;
  esac
}
