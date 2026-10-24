#!/usr/bin/env bash
# Smoke test for install.sh. Uses an isolated $HOME under mktemp.
#
# Run: ./scripts/test_install.sh
# Env: PYTHON (default python3), must be >= 3.11 for tomllib.
# Exit: 0 all passed, 1 an assertion failed, 2 PYTHON is missing or too old.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL="$REPO_ROOT/install.sh"
# Every successful install saves its options here; keep that out of the real
# state directory.
TEST_XDG_STATE_HOME="$(mktemp -d)"
export XDG_STATE_HOME="$TEST_XDG_STATE_HOME"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}
pass() { echo "ok: $*"; }

# The TOML assertions need tomllib (3.11+).
PYTHON="${PYTHON:-python3}"
# shellcheck source=scripts/require_python.sh
. "$REPO_ROOT/scripts/require_python.sh"
require_python test_install.sh "$PYTHON" || exit 2

file_inode() {
  "$PYTHON" -c 'import os, sys; print(os.stat(sys.argv[1]).st_ino)' "$1"
}

count_links() {
  # POSIX-portable: -L returns 0 only for symlinks.
  local dir="$1" n=0
  [[ -d "$dir" ]] || {
    echo 0
    return
  }
  for f in "$dir"/*; do
    [[ -L "$f" ]] && n=$((n + 1))
  done
  echo "$n"
}

# True if a skill's frontmatter marks it `activation: command`.
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
  # Count `activation: command` skills (linked as ordinary skills), optionally
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
OPENCODE_AUTO_EXPECTED="$(skill_count all opencode)"
CODEX_CMD_EXPECTED="$(command_count all codex)"
OPENCODE_CMD_EXPECTED="$(command_count all opencode)"
OPENCODE_EXPECTED=$((OPENCODE_AUTO_EXPECTED + OPENCODE_CMD_EXPECTED))
# Skills opencode links itself under --target=all: those that skip codex, so
# ~/.agents/skills (the root opencode shares) does not hold them.
OPENCODE_ONLY_EXPECTED=0
OPENCODE_ONLY_AUTO_EXPECTED=0
for _d in "$REPO_ROOT"/skills/*/; do
  [[ -f "$_d/SKILL.md" ]] || continue
  skill_is_nested_member "$_d" && continue
  skill_matches_target "$_d" opencode || continue
  skill_matches_target "$_d" codex && continue
  OPENCODE_ONLY_EXPECTED=$((OPENCODE_ONLY_EXPECTED + 1))
  skill_is_command "$_d" || OPENCODE_ONLY_AUTO_EXPECTED=$((OPENCODE_ONLY_AUTO_EXPECTED + 1))
done

run_check_tests() {
  local check_home report check_output check_status expected_row clean_home stale_home \
    agent_home guard_home untrusted_home foreign_home duplicate_home config_file instruction_file \
    output_file begin_marker end_marker all_home all_report expected_all_row legacy_venv_home
  capture_check() {
    local captured_home="$1"
    shift
    set +e
    check_output="$(HOME="$captured_home" "$INSTALL" "$@" 2>&1)"
    check_status=$?
    set -e
  }

  check_home="$(mktemp -d)"
  report="$check_home/check.tsv"
  capture_check "$check_home" --target=codex --category=communication --check --output "$report"
  [[ "$check_status" -eq 3 ]] || fail "--check reported missing managed files with exit $check_status: $check_output"
  grep -Fqx $'target\tkind\tpath\tstate' "$report" || fail "--check TSV header is missing"
  expected_row=$'codex\tskill-link\t'"$check_home"'/.agents/skills/communication-analysis'$'\tmissing'
  grep -Fq "$expected_row" "$report" ||
    fail "--check TSV did not report a missing Codex skill link"
  [[ ! -e "$check_home/.agents" && ! -e "$check_home/.codex" ]] ||
    fail "--check created files under HOME"
  pass "--check reports missing managed files as TSV without writing"

  all_home="$(mktemp -d)"
  all_report="$all_home/all-targets.tsv"
  capture_check "$all_home" --target=all --category=communication --check --output "$all_report"
  [[ "$check_status" -eq 3 ]] || fail "--check --target=all missed missing target state"
  expected_all_row=$'codex\tskill-link\t'"$all_home"'/.agents/skills/communication-analysis'$'\tmissing'
  grep -Fq "$expected_all_row" "$all_report" ||
    fail "--check --target=all did not process its resolved Codex target"
  pass "--check resolves all targets before reporting drift"

  clean_home="$(mktemp -d)"
  HOME="$clean_home" "$INSTALL" --target=codex --category=communication >/dev/null
  capture_check "$clean_home" --target=codex --category=communication --check
  [[ "$check_status" -eq 0 && "$check_output" == '--check: clean' ]] ||
    fail "--check did not report clean installed state: $check_output"
  pass "--check reports a clean managed inventory"

  stale_home="$(mktemp -d)"
  HOME="$stale_home" "$INSTALL" --target=codex --category=communication --instructions >/dev/null
  instruction_file="$stale_home/.codex/AGENTS.md"
  begin_marker='<!-- >>> agents instructions (managed by install.sh, do not edit) >>> -->'
  end_marker='<!-- <<< agents instructions <<< -->'
  printf 'notes\n\n%s\nold rules\n%s\n' "$begin_marker" "$end_marker" >"$instruction_file"
  output_file="$stale_home/instructions.tsv"
  capture_check "$stale_home" --target=codex --category=communication --instructions \
    --check --output "$output_file"
  [[ "$check_status" -eq 3 ]] || fail "stale instructions did not produce drift exit 3"
  expected_row=$'codex\tinstructions\t'"$instruction_file"$'\tstale'
  grep -Fq "$expected_row" "$output_file" || fail "--check missed stale instruction markers"
  pass "--check compares rendered instruction marker blocks"

  agent_home="$(mktemp -d)"
  HOME="$agent_home" "$INSTALL" --target=codex --category=architecture >/dev/null
  "$PYTHON" - "$agent_home/.codex/agents/coupling-analyst.toml" "$REPO_ROOT" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
path.write_text(path.read_text(encoding="utf-8").replace(sys.argv[2], "/old/checkout/agents"))
PY
  output_file="$agent_home/agents.tsv"
  capture_check "$agent_home" --target=codex --category=architecture --check --output "$output_file"
  [[ "$check_status" -eq 3 ]] || fail "moved-root Codex agent TOML did not produce drift exit 3"
  expected_row=$'codex\tcodex-agent\t'"$agent_home/.codex/agents/coupling-analyst.toml"$'\tstale'
  grep -Fq "$expected_row" "$output_file" || fail "--check missed moved-root Codex agent TOML"
  pass "--check detects moved-root paths in Codex agent TOMLs"

  guard_home="$(mktemp -d)"
  HOME="$guard_home" "$INSTALL" --target=codex --category=communication --merge-guard >/dev/null
  config_file="$guard_home/.codex/config.toml"
  "$PYTHON" - "$config_file" "$REPO_ROOT" <<'PY'
from pathlib import Path
import hashlib
import json
import sys
import tomllib

path = Path(sys.argv[1])
path.write_text(path.read_text(encoding="utf-8").replace(sys.argv[2], "/old/checkout/agents"))
config_text = path.read_text(encoding="utf-8")
config = tomllib.loads(config_text)
group = config["hooks"]["PreToolUse"][0]
handler = group["hooks"][0]
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
trusted_hash = "sha256:" + hashlib.sha256(
    json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
key = f"{path.resolve()}:pre_tool_use:0:0"
path.write_text(config_text + f'\n[hooks.state]\n{json.dumps(key)} = {{ trusted_hash = "{trusted_hash}" }}\n')
PY
  output_file="$guard_home/guards.tsv"
  capture_check "$guard_home" --target=codex --category=communication --check --output "$output_file"
  [[ "$check_status" -eq 3 ]] || fail "moved-root merge guard did not produce drift exit 3"
  expected_row=$'codex\tmerge-guard\t'"$config_file"$'\tstale'
  grep -Fq "$expected_row" "$output_file" || fail "--check missed moved-root Codex merge guard"
  ! grep -Fq $'codex\tmerge-guard\t'"$config_file"$'\tuntrusted-hook' "$output_file" ||
    fail "the saved trust hash for the old-root hook was not recognized"
  pass "--check detects moved-root Codex merge hooks"

  untrusted_home="$(mktemp -d)"
  HOME="$untrusted_home" "$INSTALL" --target=codex --category=communication \
    --merge-guard --secret-guard >/dev/null
  config_file="$untrusted_home/.codex/config.toml"
  output_file="$untrusted_home/untrusted-hooks.tsv"
  "$PYTHON" - "$config_file" <<'PY'
import json
import sys
import tomllib
from pathlib import Path

config_path = Path(sys.argv[1])
config_text = config_path.read_text(encoding="utf-8")
config = tomllib.loads(config_text)
guard_files = {"merge": "pr_merge_guard.py", "secret": "secret_read_guard.py"}
state_entries = []
for group_index, group in enumerate(config["hooks"]["PreToolUse"]):
    for handler_index, handler in enumerate(group["hooks"]):
        for guard, filename in guard_files.items():
            if filename in handler["command"]:
                key = f"{config_path.absolute()}:pre_tool_use:{group_index}:{handler_index}"
                state_entries.append((guard, key, False))
assert {guard for guard, _, _ in state_entries} == set(guard_files)
state_entries.extend(
    (None, f"/tmp/unrelated-{index}:pre_tool_use:0:0", False)
    for index in range(3)
)
state_entries.append((None, "/tmp/unrelated-enabled:pre_tool_use:0:0", True))
lines = [config_text, "", "[hooks.state]"]
for _, key, has_enabled in state_entries:
    lines.extend(["", f"[hooks.state.{json.dumps(key)}]", 'trusted_hash = "sha256:fixture-mismatch"'])
    if has_enabled:
        lines.append("enabled = true")
config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
  capture_check "$untrusted_home" --target=codex --category=communication \
    --merge-guard --secret-guard --check --output "$output_file"
  [[ "$check_status" -eq 3 ]] || fail "untrusted Codex hook did not produce drift exit 3"
  [[ "$check_output" == *'untrusted-hook=2)'* ]] || fail "summary did not count both untrusted Codex hooks"
  expected_row=$'codex\tmerge-guard\t'"$config_file"$'\tuntrusted-hook'
  grep -Fqx "$expected_row" "$output_file" || fail "--check missed untrusted Codex merge hook"
  expected_row=$'codex\tsecret-guard\t'"$config_file"$'\tuntrusted-hook'
  grep -Fqx "$expected_row" "$output_file" || fail "--check missed untrusted Codex secret hook"
  [[ "$(grep -Fc $'\tuntrusted-hook' "$output_file")" -eq 2 ]] ||
    fail "--check did not report exactly two untrusted Codex hooks"
  pass "--check reports merge and secret hooks Codex will skip until trusted"

  "$PYTHON" - "$config_file" <<'PY'
import hashlib
import json
import sys
import tomllib
from pathlib import Path

config_path = Path(sys.argv[1])
config_text = config_path.read_text(encoding="utf-8")
config = tomllib.loads(config_text)
for group_index, group in enumerate(config["hooks"]["PreToolUse"]):
    for handler_index, handler in enumerate(group["hooks"]):
        if "secret_read_guard.py" not in handler["command"]:
            continue
        normalized = {
            "type": "command",
            "command": handler["command"],
            "timeout": handler.get("timeout", 600),
            "async": handler.get("async", False),
        }
        if handler.get("statusMessage") is not None:
            normalized["statusMessage"] = handler["statusMessage"]
        identity = {
            "event_name": "pre_tool_use",
            "matcher": group.get("matcher"),
            "hooks": [normalized],
        }
        trusted_hash = "sha256:" + hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        state_key = f"{config_path.absolute()}:pre_tool_use:{group_index}:{handler_index}"
        state_header = f"[hooks.state.{json.dumps(state_key)}]"
        lines = config_text.splitlines()
        in_secret_state = False
        replaced = False
        for line_index, line in enumerate(lines):
            if line.startswith("[hooks.state.") or line == "[hooks.state]":
                in_secret_state = line == state_header
            elif line.startswith("["):
                in_secret_state = False
            elif in_secret_state and line.strip().startswith("trusted_hash ="):
                lines[line_index] = f"trusted_hash = {json.dumps(trusted_hash)}"
                replaced = True
                break
        assert replaced
        config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        raise SystemExit(0)
raise AssertionError("secret guard entry was not found")
PY
  capture_check "$untrusted_home" --target=codex --category=communication \
    --merge-guard --secret-guard --check --output "$output_file"
  [[ "$check_status" -eq 3 ]] ||
    fail "one untrusted Codex hook expected exit 3, got $check_status: $check_output"
  expected_row=$'codex\tmerge-guard\t'"$config_file"$'\tuntrusted-hook'
  grep -Fqx "$expected_row" "$output_file" || fail "--check missed the lone untrusted Codex hook"
  [[ "$(grep -Fc $'\tuntrusted-hook' "$output_file")" -eq 1 ]] ||
    fail "--check did not report exactly one untrusted Codex hook"
  pass "--check handles partial Codex guard trust state"

  foreign_home="$(mktemp -d)"
  mkdir -p "$foreign_home/.agents/skills/communication-analysis"
  output_file="$foreign_home/foreign.tsv"
  capture_check "$foreign_home" --target=codex --category=communication --check --output "$output_file"
  [[ "$check_status" -eq 3 ]] || fail "foreign managed path did not produce drift exit 3"
  expected_row=$'codex\tskill-link\t'"$foreign_home/.agents/skills/communication-analysis"$'\tforeign'
  grep -Fq "$expected_row" "$output_file" || fail "--check missed a foreign Codex skill path"
  pass "--check identifies foreign files at managed paths"

  duplicate_home="$(mktemp -d)"
  HOME="$duplicate_home" "$INSTALL" --target=codex --category=architecture >/dev/null
  config_file="$duplicate_home/.codex/config.toml"
  begin_marker='# >>> agents routed-member skill overrides (managed by install.sh, do not edit) >>>'
  end_marker='# <<< agents routed-member skill overrides <<<'
  printf '\n%s\n[[skills.config]]\npath = "/duplicate/SKILL.md"\nenabled = false\n%s\n' \
    "$begin_marker" "$end_marker" >>"$config_file"
  output_file="$duplicate_home/duplicate.tsv"
  capture_check "$duplicate_home" --target=codex --category=architecture --check --output "$output_file"
  [[ "$check_status" -eq 3 ]] || fail "duplicate managed blocks did not produce drift exit 3"
  expected_row=$'codex\trouted-member-overrides\t'"$config_file"$'\tduplicate'
  grep -Fq "$expected_row" "$output_file" || fail "--check missed duplicate managed blocks"
  pass "--check identifies duplicate managed blocks"

  legacy_venv_home="$(mktemp -d)"
  HOME="$legacy_venv_home" "$INSTALL" --target=codex --category=communication >/dev/null
  mkdir -p "$legacy_venv_home/.codex/agents-mcp-runtime"
  output_file="$legacy_venv_home/legacy-venv.tsv"
  capture_check "$legacy_venv_home" --target=codex --category=communication --check --output "$output_file"
  [[ "$check_status" -eq 3 ]] || fail "legacy MCP runtime venv did not produce drift exit 3: $check_output"
  expected_row=$'codex\tlegacy-mcp-runtime\t'"$legacy_venv_home/.codex/agents-mcp-runtime"$'\tstale'
  grep -Fq "$expected_row" "$output_file" || fail "--check missed the legacy MCP runtime venv"
  [[ -d "$legacy_venv_home/.codex/agents-mcp-runtime" ]] ||
    fail "--check deleted the legacy MCP runtime venv"
  pass "--check reports the legacy MCP runtime venv without deleting it"

  for check_args in \
    '--target=codex --check --dry-run' \
    '--target=codex --check --uninstall' \
    '--target=codex --output report.tsv' \
    '--target=bogus --check' \
    '--target=codex --check --output' \
    '--target=codex --check --output='; do
    set +e
    # Intentional word splitting turns each fixed fixture into CLI arguments.
    # shellcheck disable=SC2086
    check_output="$(HOME="$check_home" "$INSTALL" $check_args 2>&1)"
    check_status=$?
    set -e
    [[ "$check_status" -eq 2 ]] || fail "invalid --check arguments did not exit 2: $check_args"
  done
  pass "--check rejects incompatible and incomplete options"
}

run_uninstall_state_tests() {
  local home state_home state_file output status before
  capture_install() {
    set +e
    output="$(HOME="$home" XDG_STATE_HOME="$state_home" "$INSTALL" "$@" 2>&1)"
    status=$?
    set -e
  }
  saved_state_is() {
    "$PYTHON" - "$state_file" "$1" <<'PY'
import json
import sys

state = json.load(open(sys.argv[1], encoding="utf-8"))
expected = json.loads(sys.argv[2])
assert {key: state[key] for key in expected} == expected, state
PY
  }

  home="$(mktemp -d)"
  state_home="$home/xdg-state"
  state_file="$state_home/fabiandistler-agents/install.json"
  capture_install --target=codex --category=communication
  [[ "$status" -eq 0 && -f "$state_file" ]] || fail "install for uninstall test failed: $output"
  before="$(cat "$state_file")"
  capture_install --target=codex --category=communication --uninstall --dry-run
  [[ "$status" -eq 0 ]] || fail "uninstall --dry-run failed: $output"
  [[ "$output" == *"would delete install state $state_file"* ]] ||
    fail "uninstall --dry-run did not announce the state deletion"
  [[ "$(cat "$state_file")" == "$before" ]] || fail "uninstall --dry-run changed the saved state"
  capture_install --target=codex --category=communication --uninstall
  [[ "$status" -eq 0 ]] || fail "uninstall failed: $output"
  [[ ! -e "$state_file" ]] || fail "uninstall of the full saved selection kept install.json"
  capture_install --update --dry-run
  [[ "$status" -eq 4 ]] || fail "--update after a full uninstall exited $status instead of 4"
  [[ ! -e "$home/.agents/skills/documentation" ]] || fail "--update reinstalled an uninstalled skill"
  pass "full uninstall deletes the saved state, so --update has nothing to replay"

  home="$(mktemp -d)"
  state_home="$home/xdg-state"
  state_file="$state_home/fabiandistler-agents/install.json"
  capture_install --target=all --category=communication,workflow --instructions
  [[ "$status" -eq 0 ]] || fail "install for partial uninstall test failed: $output"
  capture_install --target=codex --category=communication,workflow --uninstall
  [[ "$status" -eq 0 ]] || fail "target uninstall failed: $output"
  saved_state_is '{"targets": ["claude", "opencode"], "category": "communication,workflow", "instructions": true}' ||
    fail "target uninstall did not drop just that target from the saved state"
  capture_install --target=all --category=workflow --uninstall --dry-run
  [[ "$output" == *"would rewrite install state $state_file"* ]] ||
    fail "uninstall --dry-run did not announce the state rewrite"
  capture_install --target=all --category=workflow --uninstall
  [[ "$status" -eq 0 ]] || fail "category uninstall failed: $output"
  saved_state_is '{"targets": ["claude", "opencode"], "category": "communication", "instructions": true}' ||
    fail "category uninstall did not drop just that category from the saved state"
  capture_install --update
  [[ "$status" -eq 0 ]] || fail "--update after a partial uninstall failed: $output"
  [[ ! -e "$home/.agents/skills/documentation" ]] || fail "--update reinstalled the uninstalled codex target"
  [[ -L "$home/.config/opencode/skills/documentation" ]] || fail "--update dropped the remaining opencode skills"
  [[ ! -e "$home/.config/opencode/skills/natural-planning" ]] ||
    fail "--update reinstalled the uninstalled category"
  pass "partial uninstall keeps the remaining targets and categories in the saved state"

  before="$(cat "$state_file")"
  capture_install --target=opencode --category=communication --env=chat --uninstall
  [[ "$status" -eq 0 ]] || fail "unrepresentable uninstall failed: $output"
  [[ "$output" == *"install state keeps"* ]] ||
    fail "uninstall that the state cannot express did not say so"
  [[ "$(cat "$state_file")" == "$before" ]] || fail "unrepresentable uninstall changed the saved state"
  pass "uninstall the state cannot express leaves it unchanged with a note"
}

run_update_tests() {
  local update_home state_home state_file state_copy output status instruction_file \
    move_home move_state move_file old_root moved_skill_link \
    moved_plugin_link foreign_home foreign_state foreign_agent foreign_link no_state_home no_state_dir \
    default_state_home
  capture_update() {
    local captured_home="$1" captured_state_home="$2"
    shift 2
    set +e
    output="$(HOME="$captured_home" XDG_STATE_HOME="$captured_state_home" \
      "$INSTALL" "$@" 2>&1)"
    status=$?
    set -e
  }

  update_home="$(mktemp -d)"
  state_home="$update_home/xdg-state"
  state_file="$state_home/fabiandistler-agents/install.json"
  HOME="$update_home" XDG_STATE_HOME="$state_home" "$INSTALL" \
    --target=codex --env=coding --category=architecture --instructions \
    --merge-guard --secret-guard >/dev/null
  [[ -f "$state_file" ]] || fail "successful install did not save update state"
  "$PYTHON" - "$state_file" "$REPO_ROOT" <<'PY' || fail "saved install state has the wrong schema or values"
import json
import sys

state = json.load(open(sys.argv[1], encoding="utf-8"))
assert state == {
    "targets": ["codex"],
    "env": "coding",
    "category": "architecture",
    "instructions": True,
    "merge_guard": True,
    "secret_guard": True,
    "repo_root": sys.argv[2],
}
PY
  pass "successful install saves resolved options and repo root"

  default_state_home="$(mktemp -d)"
  HOME="$default_state_home" XDG_STATE_HOME="" "$INSTALL" \
    --target=codex --category=communication >/dev/null
  [[ -f "$default_state_home/.local/state/fabiandistler-agents/install.json" ]] ||
    fail "state without XDG_STATE_HOME did not use ~/.local/state"
  pass "install state uses ~/.local/state when XDG_STATE_HOME is unset"

  no_state_home="$(mktemp -d)"
  no_state_dir="$no_state_home/xdg-state"
  capture_update "$no_state_home" "$no_state_dir" --target=codex --category=communication --dry-run
  [[ "$status" -eq 0 ]] || fail "initial dry-run failed: $output"
  [[ ! -e "$no_state_dir/fabiandistler-agents/install.json" ]] ||
    fail "dry-run saved install state"
  pass "dry-run does not save install state"

  cp "$state_file" "$update_home/state-before-update.json"
  rm "$update_home/.agents/skills/architecture"
  rm "$update_home/.codex/agents/coupling-analyst.toml"
  rm "$update_home/.agents/instructions/70-code-review-conventions.md"
  rm "$update_home/.agents/instructions/80-agent-pipelines.md"
  rm "$update_home/.agents/instructions/85-agent-scripts.md"
  instruction_file="$update_home/.codex/AGENTS.md"
  "$PYTHON" - "$instruction_file" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
content = path.read_text(encoding="utf-8").replace("For Python work, read", "old Python pointer")
path.write_text(content + "\nuser note outside the managed block\n")
PY
  capture_update "$update_home" "$state_home" --update
  [[ "$status" -eq 0 ]] || fail "--update failed to replay saved options: $output"
  [[ "$(readlink "$update_home/.agents/skills/architecture")" == "$REPO_ROOT/skills/architecture" ]] ||
    fail "--update did not restore the selected skill link"
  [[ -f "$update_home/.codex/agents/coupling-analyst.toml" ]] ||
    fail "--update did not restore the selected Codex agent"
  for payload in 70-code-review-conventions.md 80-agent-pipelines.md 85-agent-scripts.md; do
    [[ -f "$update_home/.agents/instructions/$payload" ]] ||
      fail "--update did not restore instruction payload $payload"
  done
  grep -q 'For Python work, read' "$instruction_file" ||
    fail "--update did not restore the instruction block"
  grep -q 'user note outside the managed block' "$instruction_file" ||
    fail "--update removed user text outside the instruction block"
  [[ ! -e "$update_home/.config/opencode" ]] || fail "codex-only state replay installed opencode files"
  diff -q "$state_file" "$update_home/state-before-update.json" >/dev/null ||
    fail "--update changed the saved resolved options"
  pass "--update replays filters, guards, and on-demand instruction outputs"

  rm "$update_home/.agents/skills/architecture"
  rm "$update_home/.agents/instructions/80-agent-pipelines.md"
  state_copy="$update_home/state-before-dry-run.json"
  cp "$state_file" "$state_copy"
  capture_update "$update_home" "$state_home" --update --dry-run
  [[ "$status" -eq 0 ]] || fail "--update --dry-run failed: $output"
  [[ ! -e "$update_home/.agents/skills/architecture" &&
    ! -e "$update_home/.agents/instructions/80-agent-pipelines.md" ]] ||
    fail "--update --dry-run changed managed files"
  diff -q "$state_file" "$state_copy" >/dev/null || fail "--update --dry-run changed saved state"
  pass "--update --dry-run previews without writing files or state"

  local missing_home missing_state_home
  missing_home="$(mktemp -d)"
  missing_state_home="$missing_home/empty-state"
  capture_update "$missing_home" "$missing_state_home" --update
  [[ "$status" -eq 4 ]] || fail "missing update state exited $status instead of 4"
  [[ "$output" == *'--target='* ]] || fail "missing-state error did not name --target"
  pass "--update reports missing state with its own exit code and bootstrap option"

  move_home="$(mktemp -d)"
  move_state="$move_home/xdg-state"
  move_file="$move_state/fabiandistler-agents/install.json"
  old_root="/old/checkout/agents"
  HOME="$move_home" XDG_STATE_HOME="$move_state" "$INSTALL" \
    --target=all --env=coding --category=architecture --instructions \
    --merge-guard --secret-guard >/dev/null
  "$PYTHON" - "$move_file" "$old_root" "$REPO_ROOT" "$move_home" <<'PY'
import json
from pathlib import Path
import sys

state_path = Path(sys.argv[1])
old_root, repo_root, home = sys.argv[2:]
state = json.loads(state_path.read_text(encoding="utf-8"))
assert state["targets"] == ["claude", "codex", "opencode"]
state["repo_root"] = old_root
state_path.write_text(json.dumps(state) + "\n")

config = Path(home) / ".codex/config.toml"
config.write_text(
    f"# user note: {old_root}/keep\n" +
    config.read_text(encoding="utf-8").replace(repo_root, old_root)
)
for agent in (Path(home) / ".codex/agents").glob("*.toml"):
    agent.write_text(agent.read_text(encoding="utf-8").replace(repo_root, old_root))
instructions = Path(home) / ".codex/AGENTS.md"
instructions.write_text(
    instructions.read_text(encoding="utf-8") + f"\nuser note: {old_root}/keep\n"
)
PY
  moved_skill_link="$move_home/.agents/skills/architecture"
  rm "$moved_skill_link"
  ln -s "$old_root/skills/architecture" "$moved_skill_link"
  moved_plugin_link="$move_home/.config/opencode/plugins/pr-merge-guard.js"
  rm "$moved_plugin_link"
  ln -s "$old_root/scripts/opencode/pr-merge-guard.js" "$moved_plugin_link"
  capture_update "$move_home" "$move_state" --update
  [[ "$status" -eq 0 ]] || fail "--update failed after a checkout move: $output"
  [[ "$(readlink "$moved_skill_link")" == "$REPO_ROOT/skills/architecture" ]] ||
    fail "--update did not retarget the Codex skill link from the previous checkout"
  [[ "$(readlink "$moved_plugin_link")" == "$REPO_ROOT/scripts/opencode/pr-merge-guard.js" ]] ||
    fail "--update did not retarget the OpenCode guard link from the previous checkout"
  if "$PYTHON" - "$move_home" "$move_file" "$REPO_ROOT" "$old_root" <<'PY'
import json
from pathlib import Path
import sys

home, state_path, repo_root, old_root = sys.argv[1:]
config_text = (Path(home) / ".codex/config.toml").read_text(encoding="utf-8")
assert f"# user note: {old_root}/keep" in config_text
for begin, end in (
    (
        "# >>> agents routed-member skill overrides (managed by install.sh, do not edit) >>>",
        "# <<< agents routed-member skill overrides <<<",
    ),
    (
        "# >>> agents PR merge guard (managed by install.sh, do not edit) >>>",
        "# <<< agents PR merge guard <<<",
    ),
    (
        "# >>> agents secret read guard (managed by install.sh, do not edit) >>>",
        "# <<< agents secret read guard <<<",
    ),
):
    body = config_text.split(begin, 1)[1].split(end, 1)[0]
    assert old_root not in body and repo_root in body
for agent in (Path(home) / ".codex/agents").glob("*.toml"):
    text = agent.read_text(encoding="utf-8")
    assert old_root not in text and repo_root in text
instructions = (Path(home) / ".codex/AGENTS.md").read_text(encoding="utf-8")
assert f"user note: {old_root}/keep" in instructions
assert json.loads(Path(state_path).read_text(encoding="utf-8"))["repo_root"] == repo_root
PY
  then
    :
  else
    fail "--update did not rebase marker-owned paths and preserve external content"
  fi
  pass "--update rebases marker-owned files and links after a checkout move"

  foreign_home="$(mktemp -d)"
  foreign_state="$foreign_home/xdg-state"
  HOME="$foreign_home" XDG_STATE_HOME="$foreign_state" "$INSTALL" \
    --target=codex --category=architecture >/dev/null
  foreign_agent="$foreign_home/.codex/agents/coupling-analyst.toml"
  printf 'human-owned agent\n' >"$foreign_agent"
  foreign_link="$foreign_home/.agents/skills/architecture"
  rm "$foreign_link"
  ln -s "$foreign_home/outside-skill" "$foreign_link"
  capture_update "$foreign_home" "$foreign_state" --update
  [[ "$status" -eq 0 ]] || fail "--update failed while preserving foreign paths: $output"
  [[ "$(cat "$foreign_agent")" == 'human-owned agent' ]] ||
    fail "--update overwrote a Codex agent without its marker"
  [[ "$(readlink "$foreign_link")" == "$foreign_home/outside-skill" ]] ||
    fail "--update replaced a foreign skill link"
  pass "--update preserves foreign files and links at managed paths"

  run_plain_install_after_move_test
}

# A plain install from a moved checkout saves the new repo root, so it must
# rebase the old links itself: a later --update sees equal roots and would
# leave them dangling.
run_plain_install_after_move_test() {
  local move_parent checkout_a checkout_b plain_home plain_state link dangling check_output
  move_parent="$(mktemp -d)"
  checkout_a="$move_parent/rvA"
  checkout_b="$move_parent/rvB"
  mkdir "$checkout_a"
  git -C "$REPO_ROOT" ls-files -z --cached --others --exclude-standard |
    (cd "$REPO_ROOT" && tar --null -T - -cf -) | tar -C "$checkout_a" -xf -
  plain_home="$(mktemp -d)"
  plain_state="$plain_home/xdg-state"
  HOME="$plain_home" XDG_STATE_HOME="$plain_state" \
    "$checkout_a/install.sh" --target=codex --category=communication >/dev/null
  mv "$checkout_a" "$checkout_b"
  HOME="$plain_home" XDG_STATE_HOME="$plain_state" \
    "$checkout_b/install.sh" --target=codex --category=communication >/dev/null 2>&1 ||
    fail "plain install from a moved checkout failed"
  HOME="$plain_home" XDG_STATE_HOME="$plain_state" \
    "$checkout_b/install.sh" --update >/dev/null 2>&1 ||
    fail "--update after a plain install from a moved checkout failed"
  dangling=0
  for link in "$plain_home/.agents/skills"/*; do
    [[ -L "$link" ]] || continue
    [[ "$(readlink "$link")" == "$checkout_b/"* ]] || dangling=1
  done
  ((dangling == 0)) || fail "plain install from a moved checkout left links into the old checkout"
  check_output="$(HOME="$plain_home" XDG_STATE_HOME="$plain_state" \
    "$checkout_b/install.sh" --update --check 2>&1)" ||
    fail "--update --check after a plain install from a moved checkout reported drift: $check_output"
  rm -rf "$move_parent"
  pass "plain install from a moved checkout rebases the previous checkout's links"
}

run_detected_tests() {
  local detected_home detected_state detected_bin state_file output status \
    bare_home bare_state bare_bin no_agent_home no_agent_state

  detected_home="$(mktemp -d)"
  detected_state="$detected_home/xdg-state"
  detected_bin="$detected_home/bin"
  mkdir -p "$detected_bin" "$detected_home/.codex" "$detected_home/.config/opencode"
  printf '#!/bin/sh\nexit 0\n' >"$detected_bin/claude"
  chmod +x "$detected_bin/claude"
  [[ ! -d "$detected_home/.claude" ]] || fail "CLI detection fixture already has Claude config"
  set +e
  output="$(HOME="$detected_home" XDG_STATE_HOME="$detected_state" \
    PATH="$detected_bin:$PATH" "$INSTALL" --target=detected --category=communication 2>&1)"
  status=$?
  set -e
  [[ "$status" -eq 0 ]] || fail "--target=detected failed: $output"
  [[ "$output" == *'detected targets: claude, codex, opencode'* ]] ||
    fail "--target=detected did not print its resolved targets: $output"
  state_file="$detected_state/fabiandistler-agents/install.json"
  if "$PYTHON" - "$state_file" <<'PY'
import json
import sys

targets = json.load(open(sys.argv[1], encoding="utf-8"))["targets"]
assert targets == ["claude", "codex", "opencode"]
assert "detected" not in targets
PY
  then
    :
  else
    fail "detected install did not save resolved targets"
  fi
  cp "$state_file" "$detected_home/state-before-check.json"
  set +e
  output="$(HOME="$detected_home" XDG_STATE_HOME="$detected_state" \
    PATH="$detected_bin:$PATH" "$INSTALL" --target=detected --category=communication --check 2>&1)"
  status=$?
  set -e
  [[ "$status" -eq 0 && "$output" == *'--check: clean'* ]] ||
    fail "--check did not resolve detected targets read-only: $output"
  diff -q "$state_file" "$detected_home/state-before-check.json" >/dev/null ||
    fail "--check with detected targets changed saved install state"
  pass "--target=detected combines installed commands and config directories"

  bare_home="$(mktemp -d)"
  bare_state="$bare_home/xdg-state"
  bare_bin="$(mktemp -d)"
  ln -s "$(command -v bash)" "$bare_bin/bash"
  ln -s "$(command -v dirname)" "$bare_bin/dirname"
  ln -s "$(command -v sed)" "$bare_bin/sed"
  ln -s "$(command -v cat)" "$bare_bin/cat"
  set +e
  output="$(HOME="$bare_home" XDG_STATE_HOME="$bare_state" PATH="$bare_bin" \
    "$INSTALL" 2>&1)"
  status=$?
  set -e
  [[ "$status" -eq 2 && "$output" == *'missing --target=claude|codex|opencode|all|detected'* ]] ||
    fail "bare installer invocation did not explain the target options: $output"
  [[ ! -e "$bare_home/.agents" && ! -e "$bare_home/.codex" &&
    ! -e "$bare_home/.claude" && ! -e "$bare_home/.config" &&
    ! -e "$bare_state/fabiandistler-agents/install.json" ]] ||
    fail "bare installer invocation wrote into HOME or XDG state"
  pass "bare invocation exits 2 without writing and lists detected"

  no_agent_home="$(mktemp -d)"
  no_agent_state="$no_agent_home/xdg-state"
  set +e
  output="$(HOME="$no_agent_home" XDG_STATE_HOME="$no_agent_state" PATH="$bare_bin" \
    "$INSTALL" --target=detected 2>&1)"
  status=$?
  set -e
  [[ "$status" -eq 2 && "$output" == *'no agent commands or config directories detected'* ]] ||
    fail "empty detected target set did not exit 2 clearly: $output"
  [[ ! -e "$no_agent_home/.agents" && ! -e "$no_agent_home/.codex" &&
    ! -e "$no_agent_home/.claude" && ! -e "$no_agent_home/.config" &&
    ! -e "$no_agent_state/fabiandistler-agents/install.json" ]] ||
    fail "empty detected target set wrote into HOME or XDG state"
  pass "--target=detected with no installations exits 2 without writing"
}

run_git_hook_tests() {
  local hook_home state_home git_home git_dir hooks_dir post_merge post_rewrite \
    skill_link before_merge before_rewrite output status dry_home dry_state dry_git_home \
    dry_git_dir foreign_home foreign_state foreign_git_home foreign_git_dir foreign_hooks \
    foreign_merge foreign_rewrite foreign_content

  capture_hook_install() {
    local captured_home="$1" captured_state="$2" captured_git_dir="$3"
    shift 3
    set +e
    output="$(HOME="$captured_home" XDG_STATE_HOME="$captured_state" \
      GIT_DIR="$captured_git_dir" GIT_WORK_TREE="$REPO_ROOT" \
      "$INSTALL" "$@" 2>&1)"
    status=$?
    set -e
  }

  capture_hook_run() {
    local hook="$1" captured_home="$2" captured_state="$3" captured_git_dir="$4" input="$5"
    set +e
    output="$(cd "$REPO_ROOT" && printf '%s' "$input" |
      HOME="$captured_home" XDG_STATE_HOME="$captured_state" \
        GIT_DIR="$captured_git_dir" GIT_WORK_TREE="$REPO_ROOT" "$hook" 2>&1)"
    status=$?
    set -e
  }

  hook_home="$(mktemp -d)"
  state_home="$hook_home/xdg-state"
  git_home="$(mktemp -d)"
  git -C "$git_home" init -q
  git_dir="$git_home/.git"
  hooks_dir="$git_dir/hooks"
  post_merge="$hooks_dir/post-merge"
  post_rewrite="$hooks_dir/post-rewrite"
  capture_hook_install "$hook_home" "$state_home" "$git_dir" \
    --target=codex --category=communication --git-hook
  [[ "$status" -eq 0 ]] || fail "--git-hook install failed: $output"
  [[ -x "$post_merge" && -x "$post_rewrite" ]] ||
    fail "--git-hook did not create executable post-merge and post-rewrite hooks"
  grep -Fqx '# managed-by: fabiandistler/agents install.sh' "$post_merge" ||
    fail "post-merge hook is missing its ownership marker"
  grep -Fqx '# managed-by: fabiandistler/agents install.sh' "$post_rewrite" ||
    fail "post-rewrite hook is missing its ownership marker"
  [[ "$(head -n 1 "$post_rewrite")" == '#!/bin/sh' &&
  "$(sed -n '3p' "$post_rewrite")" == 'cat >/dev/null' ]] ||
    fail "post-rewrite hook does not consume Git's rewrite list"
  [[ -f "$state_home/fabiandistler-agents/install.json" ]] ||
    fail "--git-hook install did not save replay state"
  before_merge="$(cat "$post_merge")"
  before_rewrite="$(cat "$post_rewrite")"
  capture_hook_install "$hook_home" "$state_home" "$git_dir" \
    --target=codex --category=communication --git-hook
  [[ "$status" -eq 0 ]] || fail "reinstalling --git-hook failed: $output"
  [[ "$(cat "$post_merge")" == "$before_merge" &&
  "$(cat "$post_rewrite")" == "$before_rewrite" ]] ||
    fail "reinstalling --git-hook rewrote unchanged hooks"
  [[ "$output" == *"ok        $post_merge (Git hook)"* &&
    "$output" == *"ok        $post_rewrite (Git hook)"* ]] ||
    fail "reinstalling --git-hook did not report both hooks unchanged"
  pass "--git-hook creates executable marker-owned hooks idempotently"

  skill_link="$hook_home/.agents/skills/communication-analysis"
  rm "$skill_link"
  capture_hook_run "$post_merge" "$hook_home" "$state_home" "$git_dir" ""
  [[ "$status" -eq 0 && "$output" == *'--check: drift'* && -L "$skill_link" ]] ||
    fail "post-merge did not check and replay the saved install: $output"
  if "$PYTHON" - "$output" "$skill_link" "$REPO_ROOT" <<'PY'
import sys

output, skill_link, repo_root = sys.argv[1:]
check = output.index("--check: drift")
update = output.index(f"linked    {skill_link} -> {repo_root}/skills/communication-analysis")
assert check < update
PY
  then
    :
  else
    fail "post-merge ran --update before its --check"
  fi
  pass "post-merge checks first, then replays only when drift exists"

  capture_hook_run "$post_rewrite" "$hook_home" "$state_home" "$git_dir" "old new\n"
  [[ "$status" -eq 0 && "$output" == '--check: clean' ]] ||
    fail "clean post-rewrite did not stop after its read-only check: $output"
  rm "$skill_link"
  capture_hook_run "$post_rewrite" "$hook_home" "$state_home" "$git_dir" "old new\n"
  [[ "$status" -eq 0 && "$output" == *'--check: drift'* && -L "$skill_link" ]] ||
    fail "post-rewrite did not consume stdin and replay drift: $output"
  pass "post-rewrite consumes rewrite input and checks before updating"

  capture_hook_install "$hook_home" "$state_home" "$git_dir" --uninstall --git-hook
  [[ "$status" -eq 0 && ! -e "$post_merge" && ! -e "$post_rewrite" ]] ||
    fail "targetless --uninstall --git-hook did not remove both managed hooks: $output"
  pass "--uninstall --git-hook removes only this clone's managed hooks"

  dry_home="$(mktemp -d)"
  dry_state="$dry_home/xdg-state"
  dry_git_home="$(mktemp -d)"
  git -C "$dry_git_home" init -q
  dry_git_dir="$dry_git_home/.git"
  capture_hook_install "$dry_home" "$dry_state" "$dry_git_dir" \
    --target=codex --category=communication --git-hook --dry-run
  [[ "$status" -eq 0 && ! -e "$dry_git_dir/hooks/post-merge" &&
    ! -e "$dry_git_dir/hooks/post-rewrite" ]] ||
    fail "--git-hook --dry-run wrote into the Git hooks directory"
  pass "--git-hook --dry-run creates no hooks"

  foreign_home="$(mktemp -d)"
  foreign_state="$foreign_home/xdg-state"
  foreign_git_home="$(mktemp -d)"
  git -C "$foreign_git_home" init -q
  foreign_git_dir="$foreign_git_home/.git"
  foreign_hooks="$foreign_git_dir/hooks"
  foreign_merge="$foreign_hooks/post-merge"
  foreign_rewrite="$foreign_hooks/post-rewrite"
  foreign_content=$'#!/bin/sh\n# human-owned hook\nexit 0'
  printf '%b\n' "$foreign_content" >"$foreign_merge"
  chmod +x "$foreign_merge"
  capture_hook_install "$foreign_home" "$foreign_state" "$foreign_git_dir" \
    --target=codex --category=communication --git-hook
  [[ "$status" -eq 0 && "$(cat "$foreign_merge")" == "$foreign_content" &&
  -x "$foreign_rewrite" ]] ||
    fail "--git-hook overwrote a foreign hook or failed to install the other hook: $output"
  capture_hook_install "$foreign_home" "$foreign_state" "$foreign_git_dir" \
    --uninstall --git-hook
  [[ "$status" -eq 0 && "$(cat "$foreign_merge")" == "$foreign_content" &&
  ! -e "$foreign_rewrite" ]] ||
    fail "--uninstall --git-hook removed a foreign hook or kept its managed hook"
  pass "foreign post-merge hooks survive install and uninstall"
}

run_opencode_agent_tests() {
  local agent_home state_home state_file agents_dir coupling cohesion removed before output status old_root \
    edit_source rendered marker
  agent_home="$(mktemp -d)"
  state_home="$agent_home/xdg-state"
  agents_dir="$agent_home/.config/opencode/agents"
  HOME="$agent_home" XDG_STATE_HOME="$state_home" "$INSTALL" \
    --target=opencode --category=architecture >/dev/null
  coupling="$agents_dir/coupling-analyst.md"
  cohesion="$agents_dir/cohesion-analyst.md"
  removed="$agents_dir/source-removed.md"
  state_file="$state_home/fabiandistler-agents/install.json"
  [[ -f "$coupling" && -f "$cohesion" ]] ||
    fail "OpenCode install did not render selected plugin agents in agents/"
  [[ ! -e "$agent_home/.config/opencode/agent" ]] ||
    fail "OpenCode install wrote plugin agents to the legacy singular agent/ directory"
  if "$PYTHON" - "$agents_dir" "$REPO_ROOT" <<'PY'
from pathlib import Path
import sys

agents_dir = Path(sys.argv[1])
repo_root = Path(sys.argv[2])
marker = "# generated by fabiandistler/agents install.sh; do not edit"
for name in ("coupling-analyst", "cohesion-analyst"):
    text = (agents_dir / f"{name}.md").read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    body = text.split("---", 2)[2]
    assert marker in frontmatter
    assert "description: \"" in frontmatter
    assert "mode: subagent" in frontmatter
    # A Claude tools: list is an allowlist: the catch-all deny must come first,
    # because OpenCode lets the last matching rule win.
    permission_block = frontmatter.split("permission:\n", 1)[1].split("\n")
    assert permission_block[0] == '  "*": deny'
    assert "  read: allow" in frontmatter
    assert "  grep: allow" in frontmatter
    assert "  glob: allow" in frontmatter
    assert "  bash: allow" in frontmatter
    assert "shell:" not in frontmatter
    for unlisted in ("edit", "webfetch", "websearch", "task"):
        assert f"  {unlisted}: allow" not in frontmatter
    assert "model:" not in frontmatter
    assert "${CLAUDE_PLUGIN_ROOT}" not in text
    assert str(repo_root / "plugins/architecture") in body
assert "Read-only coupling analysis of a codebase." in (
    agents_dir / "coupling-analyst.md"
).read_text(encoding="utf-8")
PY
  then
    :
  else
    fail "OpenCode agent render was incomplete"
  fi
  pass "OpenCode agents preserve descriptions and map tool permissions"

  local resolved
  # Optional: only a binary that runs under the temp HOME can resolve the
  # rendered agents; wrapper installs that need the real HOME are skipped.
  if ! command -v opencode >/dev/null 2>&1 ||
    ! resolved="$(cd "$agent_home" && HOME="$agent_home" XDG_CONFIG_HOME="$agent_home/.config" \
      XDG_DATA_HOME="$agent_home/.local/share" XDG_STATE_HOME="$state_home" \
      XDG_CACHE_HOME="$agent_home/.cache" opencode agent list 2>/dev/null)"; then
    echo "skip: opencode cannot run under a temp HOME; resolved-permission check skipped"
  else
    if printf '%s' "$resolved" | "$PYTHON" -c '
import json, sys

text = sys.stdin.read()
section = text[text.index("coupling-analyst (subagent)"):]
start = section.index("[")
rules, _ = json.JSONDecoder().raw_decode(section[start:])

def action(permission):
    matching = [r for r in rules if r["permission"] in (permission, "*") and r["pattern"] == "*"]
    return matching[-1]["action"]

assert action("bash") == "allow"
assert action("read") == "allow"
for denied in ("edit", "webfetch", "websearch", "task"):
    assert action(denied) == "deny", denied
'; then
      pass "opencode resolves the analyst permissions as an allowlist"
    else
      fail "opencode did not resolve the analyst permissions as an allowlist"
    fi
  fi

  edit_source="$agent_home/writable-agent.md"
  marker='# generated by fabiandistler/agents install.sh; do not edit'
  cat >"$edit_source" <<'AGENT'
---
name: writable-agent
description: Writable test agent.
tools: Read, Edit, Write
model: sonnet
---
The prompt can write when asked.
AGENT
  rendered="$(python3 "$REPO_ROOT/scripts/plugin_agents.py" opencode \
    --source "$edit_source" --plugin-dir "$REPO_ROOT/plugins/architecture" --marker "$marker")"
  [[ "$rendered" == *'  edit: allow'* && "$rendered" != *'  edit: deny'* ]] ||
    fail "OpenCode did not map Edit/Write tools to edit permission"
  pass "OpenCode maps Edit and Write tools to edit allow"

  before="$(cat "$coupling")"
  output="$(HOME="$agent_home" XDG_STATE_HOME="$state_home" \
    "$INSTALL" --target=opencode --category=architecture 2>&1)"
  [[ "$(cat "$coupling")" == "$before" && "$output" == *"ok        $coupling (opencode-agent)"* ]] ||
    fail "OpenCode agent install was not idempotent: $output"
  old_root="/old/checkout/agents"
  "$PYTHON" - "$state_file" "$coupling" "$REPO_ROOT" "$old_root" <<'PY'
import json
from pathlib import Path
import sys

state_path, agent_path, repo_root, old_root = sys.argv[1:]
state_file = Path(state_path)
state = json.loads(state_file.read_text(encoding="utf-8"))
state["repo_root"] = old_root
state_file.write_text(json.dumps(state) + "\n", encoding="utf-8")
agent_file = Path(agent_path)
agent_file.write_text(
    agent_file.read_text(encoding="utf-8").replace(repo_root, old_root),
    encoding="utf-8",
)
PY
  output="$(HOME="$agent_home" XDG_STATE_HOME="$state_home" "$INSTALL" --update 2>&1)"
  if "$PYTHON" - "$state_file" "$coupling" "$REPO_ROOT" "$old_root" <<'PY'
import json
from pathlib import Path
import sys

state_path, agent_path, repo_root, old_root = sys.argv[1:]
state = json.loads(Path(state_path).read_text(encoding="utf-8"))
agent = Path(agent_path).read_text(encoding="utf-8")
assert state["repo_root"] == repo_root
assert old_root not in agent and repo_root in agent
PY
  then
    :
  else
    fail "--update did not rebase the moved OpenCode agent"
  fi
  printf '%s\n' '---' '# generated by fabiandistler/agents install.sh; do not edit' \
    'name: removed' '---' 'stale prompt' >"$removed"
  rm "$coupling"
  output="$(HOME="$agent_home" XDG_STATE_HOME="$state_home" "$INSTALL" --update 2>&1)"
  [[ -f "$coupling" && ! -e "$removed" && "$output" == *'agent no longer in repo'* ]] ||
    fail "--update did not restore and prune OpenCode agents: $output"
  pass "OpenCode agent install is idempotent and --update restores/prunes outputs"

  printf '%s\n' 'human-owned OpenCode agent' >"$cohesion"
  output="$(HOME="$agent_home" XDG_STATE_HOME="$state_home" \
    "$INSTALL" --target=opencode --category=architecture 2>&1)"
  [[ "$(cat "$cohesion")" == 'human-owned OpenCode agent' ]] ||
    fail "OpenCode install overwrote a foreign agent"
  HOME="$agent_home" XDG_STATE_HOME="$state_home" "$INSTALL" \
    --target=opencode --category=architecture --uninstall >/dev/null 2>&1
  [[ ! -e "$coupling" && "$(cat "$cohesion")" == 'human-owned OpenCode agent' ]] ||
    fail "OpenCode uninstall did not remove only generated agents"
  pass "OpenCode uninstall removes generated agents and preserves foreign files"
}
run_command_skill_tests() {
  local command_home state_home skills_dir legacy_dir skill_link legacy_link \
    foreign_dir foreign_link output skill_md activation
  command_home="$(mktemp -d)"
  state_home="$command_home/xdg-state"
  skills_dir="$command_home/.config/opencode/skills"
  legacy_dir="$command_home/.config/opencode/command"
  skill_link="$skills_dir/repo-status"

  HOME="$command_home" XDG_STATE_HOME="$state_home" "$INSTALL" \
    --target=opencode --category=workflow >/dev/null
  [[ -L "$skill_link" && "$(readlink "$skill_link")" == "$REPO_ROOT/skills/repo-status" ]] ||
    fail "OpenCode command skill was not installed as an ordinary skills link"
  [[ ! -e "$legacy_dir" ]] ||
    fail "OpenCode install created its legacy singular command directory"

  for skill_md in "$REPO_ROOT"/skills/*/SKILL.md; do
    activation="$(sed -n 's/^activation:[[:space:]]*//p' "$skill_md")"
    [[ "$activation" == command ]] || continue
    "$PYTHON" "$REPO_ROOT/scripts/quick_validate.py" "${skill_md%/SKILL.md}" >/dev/null ||
      fail "quick_validate rejected command skill ${skill_md%/SKILL.md}"
  done
  pass "OpenCode command skills install in skills/ and pass shared validation"

  mkdir -p "$legacy_dir"
  legacy_link="$legacy_dir/repo-status.md"
  ln -s "$REPO_ROOT/skills/repo-status/SKILL.md" "$legacy_link"
  foreign_dir="$(mktemp -d)/foreign-command"
  mkdir "$foreign_dir"
  foreign_link="$legacy_dir/foreign.md"
  ln -s "$foreign_dir" "$foreign_link"
  output="$(HOME="$command_home" XDG_STATE_HOME="$state_home" \
    "$INSTALL" --target=opencode --category=workflow 2>&1)"
  [[ ! -L "$legacy_link" && -L "$foreign_link" && -L "$skill_link" ]] ||
    fail "legacy command migration removed a foreign path or lost the skill link: $output"
  pass "legacy OpenCode command links migrate without touching foreign entries"

  HOME="$command_home" XDG_STATE_HOME="$state_home" "$INSTALL" \
    --target=opencode --category=workflow --uninstall >/dev/null
  [[ ! -e "$skill_link" && ! -e "$legacy_link" && -L "$foreign_link" ]] ||
    fail "OpenCode command-skill uninstall removed a foreign path or kept the link"
  pass "OpenCode command-skill uninstall removes only repo-owned links"
}

# Exercises the hooks through real git operations in a throwaway copy of this
# checkout, so linked worktrees and core.hooksPath behave as they do for users.
run_git_hook_worktree_tests() {
  local sandbox main_clone linked home state skill_link output status

  sandbox_git() {
    HOME="$home" XDG_STATE_HOME="$state" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
      GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.invalid \
      GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.invalid git "$@"
  }

  sandbox_install() {
    local checkout="$1"
    shift
    set +e
    output="$(HOME="$home" XDG_STATE_HOME="$state" GIT_CONFIG_GLOBAL=/dev/null \
      GIT_CONFIG_NOSYSTEM=1 "$checkout/install.sh" "$@" 2>&1)"
    status=$?
    set -e
  }

  fresh_sandbox() {
    sandbox="$(cd "$(mktemp -d)" && pwd -P)"
    home="$sandbox/home"
    state="$sandbox/state"
    main_clone="$sandbox/main"
    linked="$sandbox/linked"
    mkdir -p "$home" "$main_clone"
    git -C "$REPO_ROOT" ls-files -z | (cd "$REPO_ROOT" && tar --null -T - -cf -) |
      tar -C "$main_clone" -xf -
    sandbox_git -C "$main_clone" init -q -b main
    sandbox_git -C "$main_clone" add -A
    sandbox_git -C "$main_clone" commit -q -m sandbox
    sandbox_git -C "$main_clone" branch topic
    sandbox_git -C "$main_clone" worktree add -q "$linked" -b side
    skill_link="$home/.agents/skills/communication-analysis"
  }

  fresh_sandbox
  sandbox_install "$main_clone" --target=codex --category=communication --git-hook
  [[ "$status" -eq 0 ]] || fail "--git-hook install in the sandbox clone failed: $output"
  sandbox_git -C "$main_clone" switch -q topic
  echo topic >"$main_clone/topic.txt"
  sandbox_git -C "$main_clone" add topic.txt
  sandbox_git -C "$main_clone" commit -q -m topic
  sandbox_git -C "$main_clone" switch -q main
  rm "$skill_link"
  sandbox_git -C "$linked" merge -q --no-edit topic >/dev/null 2>&1
  [[ ! -e "$skill_link" && ! -L "$skill_link" ]] ||
    fail "a merge in a linked worktree replayed the install from that worktree"
  sandbox_git -C "$main_clone" merge -q --no-edit topic >/dev/null 2>&1
  [[ "$(readlink "$skill_link")" == "$main_clone/skills/communication-analysis" ]] ||
    fail "a merge in the installing clone did not replay the install into it"
  pass "post-merge replays only for the installing checkout, not linked worktrees"

  fresh_sandbox
  sandbox_install "$linked" --target=codex --category=communication --git-hook
  [[ "$status" -eq 0 && -x "$main_clone/.git/hooks/post-merge" &&
    -x "$main_clone/.git/hooks/post-rewrite" &&
    ! -e "$main_clone/.git/worktrees/linked/hooks/post-merge" &&
    "$output" == *"created   $main_clone/.git/hooks/post-merge (Git hook)"* ]] ||
    fail "--git-hook from a linked worktree did not write the common hooks dir: $output"
  pass "--git-hook from a linked worktree writes the hooks Git actually runs"

  fresh_sandbox
  sandbox_git -C "$main_clone" config core.hooksPath .husky
  sandbox_install "$main_clone" --target=codex --category=communication --git-hook
  [[ "$status" -eq 1 && "$output" == *'core.hooksPath is set'* &&
    ! -e "$main_clone/.husky" && ! -e "$main_clone/.git/hooks/post-merge" &&
    ! -e "$home/.agents" && ! -e "$state/fabiandistler-agents/install.json" ]] ||
    fail "--git-hook with core.hooksPath did not refuse before writing: $output"
  pass "--git-hook refuses with exit 1 when core.hooksPath is set"
}

# 1. dry-run for --target=all should not create anything.
HOME_DRY="$(mktemp -d)"
dry_output="$(HOME="$HOME_DRY" "$INSTALL" --target=all --dry-run 2>&1)"
[[ ! -d "$HOME_DRY/.claude" ]] || fail "dry-run created $HOME_DRY/.claude"
[[ ! -d "$HOME_DRY/.codex" ]] || fail "dry-run created $HOME_DRY/.codex"
[[ ! -d "$HOME_DRY/.config/opencode" ]] || fail "dry-run created $HOME_DRY/.config/opencode"
[[ "$(grep -c '^\[dry-run\] write .*/\.codex/agents/.*\.toml$' <<<"$dry_output")" -eq 2 ]] ||
  fail "dry-run agent writes were not one target-only line each"
pass "dry-run creates no files"

# 2. install --target=claude links nothing: Claude gets skills, commands,
#    subagents and the merge guard from the plugin marketplace (#567).
HOME_C="$(mktemp -d)"
HOME="$HOME_C" "$INSTALL" --target=claude >/dev/null
[[ ! -e "$HOME_C/.claude/skills" ]] || fail "claude install created ~/.claude/skills"
[[ ! -e "$HOME_C/.claude/commands" ]] || fail "claude install created ~/.claude/commands"
[[ ! -e "$HOME_C/.claude/settings.json" ]] || fail "claude install created settings.json"
pass "claude install links no skills or commands"

# 3. Migration from a symlink install: every claude run removes our skill and
#    command links (live and dangling) and the old merge-guard entry in
#    settings.json; foreign links and settings stay. A dry-run only reports.
make_claude_symlink_home() {
  local home="$1"
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
foreign_src="$(mktemp -d)/foreign"
mkdir "$foreign_src"
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
pass "claude install migrates symlinks and the settings.json guard away"

# 4. --uninstall runs the same migration, whatever --category says.
HOME_MIGU="$(mktemp -d)"
make_claude_symlink_home "$HOME_MIGU"
HOME="$HOME_MIGU" "$INSTALL" --target=claude --category=workflow --uninstall >/dev/null
[[ "$(count_links "$HOME_MIGU/.claude/skills")" -eq 1 ]] || fail "claude uninstall left our skill links"
[[ "$(count_links "$HOME_MIGU/.claude/commands")" -eq 1 ]] || fail "claude uninstall left our command links"
! grep -q pr_merge_guard "$HOME_MIGU/.claude/settings.json" || fail "claude uninstall left the guard entry"
pass "claude uninstall migrates too, ignoring --category"

# 5. A settings.json that is not a JSON object is left untouched.
HOME_BADJ="$(mktemp -d)"
mkdir -p "$HOME_BADJ/.claude"
printf '["pr_merge_guard.py"]\n' >"$HOME_BADJ/.claude/settings.json"
HOME="$HOME_BADJ" "$INSTALL" --target=claude >/dev/null 2>&1
[[ "$(cat "$HOME_BADJ/.claude/settings.json")" == '["pr_merge_guard.py"]' ]] ||
  fail "migration rewrote a settings.json that is not an object"
pass "migration leaves a non-object settings.json alone"

# 5a. --env or --category with a claude target prints exactly one WARN line
#     (they have no effect there) and keeps the exit code; other targets and a
#     plain claude run stay quiet.
claude_filter_warns() {
  local err
  err="$(HOME="$(mktemp -d)" "$INSTALL" "$@" 2>&1 >/dev/null)" ||
    fail "install.sh $* exited non-zero"
  grep -c 'WARN .*no effect for claude' <<<"$err" || true
}
[[ "$(claude_filter_warns --target=claude --category=workflow)" -eq 1 ]] ||
  fail "--category with --target=claude did not warn once"
[[ "$(claude_filter_warns --target=all --env=chat --category=workflow --dry-run)" -eq 1 ]] ||
  fail "--env/--category with --target=all did not warn once"
[[ "$(claude_filter_warns --target=claude)" -eq 0 ]] || fail "plain claude run warned"
[[ "$(claude_filter_warns --target=opencode --env=chat --dry-run)" -eq 0 ]] ||
  fail "--env with --target=opencode warned about claude"
pass "--env/--category with a claude target warn once, exit code unchanged"

# 6. install --target=all populates codex and opencode only. Both runtimes
#    install command skills in their normal skills roots.
CODEX_SKILLS_EXPECTED=$((CODEX_EXPECTED + CODEX_CMD_EXPECTED))
HOME_A="$(mktemp -d)"
HOME="$HOME_A" "$INSTALL" --target=all >/dev/null
[[ ! -e "$HOME_A/.claude" ]] || fail "all install created ~/.claude"
got="$(count_links "$HOME_A/.config/opencode/skills")"
[[ "$got" -eq "$OPENCODE_ONLY_EXPECTED" ]] ||
  fail "all install: opencode skills has $got links, expected $OPENCODE_ONLY_EXPECTED"
got="$(count_links "$HOME_A/.agents/skills")"
[[ "$got" -eq "$CODEX_SKILLS_EXPECTED" ]] ||
  fail "all install: .agents/skills has $got links, expected $CODEX_SKILLS_EXPECTED"
[[ ! -e "$HOME_A/.config/opencode/command" ]] ||
  fail "all install created the legacy OpenCode command directory"
[[ -L "$HOME_A/.agents/skills/repo-status" ]] || fail "codex: command skill repo-status not linked into skills/"
[[ -f "$HOME_A/.agents/skills/repo-status/agents/openai.yaml" ]] ||
  fail "codex: command skill repo-status missing its openai.yaml sidecar"
[[ ! -e "$HOME_A/.codex/prompts/repo-status.md" ]] || fail "codex: command skill repo-status leaked into deprecated prompts/"
documentation_link="$HOME_A/.agents/skills/documentation"
link_inode_before="$(stat -c %i "$documentation_link")"
reinstall_output="$(HOME="$HOME_A" "$INSTALL" --target=all 2>&1)"
[[ "$(stat -c %i "$documentation_link")" == "$link_inode_before" ]] ||
  fail "reinstall replaced an unchanged skill link"
grep -q '^  ok .*\.agents/skills/documentation' <<<"$reinstall_output" ||
  fail "reinstall did not report the unchanged skill link as ok"
pass "all install populates codex and opencode; unchanged links retain their inode"

# 6a. --uninstall removes command-skill links from the normal skill roots.
HOME="$HOME_A" "$INSTALL" --target=all --uninstall >/dev/null
[[ ! -e "$HOME_A/.agents/skills/repo-status" ]] || fail "codex uninstall left command skill repo-status behind"
[[ ! -e "$HOME_A/.config/opencode/skills/repo-status" ]] ||
  fail "OpenCode uninstall left command skill repo-status in skills/"
pass "all uninstall removes command skills from the normal skill roots"

# 6aa. re-running an install keeps the existing skill symlink inode.
HOME_LINK_IDEM="$(mktemp -d)"
HOME="$HOME_LINK_IDEM" "$INSTALL" --target=opencode --category=workflow >/dev/null
IDEM_LINK="$HOME_LINK_IDEM/.config/opencode/skills/natural-planning"
link_inode_before="$(file_inode "$IDEM_LINK")"
link_output="$(HOME="$HOME_LINK_IDEM" "$INSTALL" --target=opencode --category=workflow 2>&1)"
[[ "$(file_inode "$IDEM_LINK")" == "$link_inode_before" ]] ||
  fail "reinstall rewrote an unchanged skill link"
grep -q '  ok .*natural-planning' <<<"$link_output" ||
  fail "reinstall did not report the unchanged skill link as ok"
echo "ok: unchanged skill links keep their inode"

# 6f. opencode reads ~/.agents/skills too, and wants skill names unique across
#     its roots (#564): with codex installed first, opencode links none of the
#     shared skills, including command skills.
HOME_OCS="$(mktemp -d)"
OCS_SKILLS="$HOME_OCS/.config/opencode/skills"
HOME="$HOME_OCS" "$INSTALL" --target=codex >/dev/null
HOME="$HOME_OCS" "$INSTALL" --target=opencode >/dev/null
got="$(count_links "$OCS_SKILLS")"
[[ "$got" -eq "$OPENCODE_ONLY_EXPECTED" ]] || fail "opencode after codex: $got duplicate skill links"
[[ ! -e "$HOME_OCS/.config/opencode/command" ]] ||
  fail "opencode after codex created the legacy command directory"
pass "opencode skips skills codex already links"

# 6g. the reverse order ends in the same state: a codex install removes the
#     opencode links it now shadows, a foreign entry there survives, and
#     uninstalling codex alone says how to restore opencode's own links.
HOME_OCR="$(mktemp -d)"
OCR_SKILLS="$HOME_OCR/.config/opencode/skills"
HOME="$HOME_OCR" "$INSTALL" --target=opencode >/dev/null
got="$(count_links "$OCR_SKILLS")"
[[ "$got" -eq "$OPENCODE_EXPECTED" ]] || fail "opencode alone: expected $OPENCODE_EXPECTED links, got $got"
foreign_oc="$(mktemp -d)/foreign"
mkdir "$foreign_oc"
ln -s "$foreign_oc" "$OCR_SKILLS/foreign-skill"
HOME="$HOME_OCR" "$INSTALL" --target=codex --dry-run >/dev/null
got="$(count_links "$OCR_SKILLS")"
[[ "$got" -eq $((OPENCODE_EXPECTED + 1)) ]] || fail "dry-run removed opencode links"
HOME="$HOME_OCR" "$INSTALL" --target=codex >/dev/null
got="$(count_links "$OCR_SKILLS")"
[[ "$got" -eq $((OPENCODE_ONLY_EXPECTED + 1)) && -L "$OCR_SKILLS/foreign-skill" ]] ||
  fail "codex after opencode: expected only the foreign link, found $got links"
oc_note="$(HOME="$HOME_OCR" "$INSTALL" --target=codex --uninstall 2>&1 >/dev/null)"
grep -q 'note .*re-run --target=opencode' <<<"$oc_note" ||
  fail "codex uninstall did not tell how to restore opencode's links"
HOME="$HOME_OCR" "$INSTALL" --target=opencode >/dev/null
got="$(count_links "$OCR_SKILLS")"
[[ "$got" -eq $((OPENCODE_EXPECTED + 1)) ]] || fail "opencode re-run: expected all links back, got $got"
pass "codex and opencode, in either order, leave opencode no duplicate links"

# 6h. a narrower --env for codex leaves the rest to opencode's own links, and
#     a whole-tree dry-run plans exactly what the real run does.
HOME_OCE="$(mktemp -d)"
HOME="$HOME_OCE" "$INSTALL" --target=codex --env=chat >/dev/null
HOME="$HOME_OCE" "$INSTALL" --target=opencode >/dev/null
shared=0
for link in "$HOME_OCE/.agents/skills"/*; do
  [[ -L "$link" ]] || continue
  skill_matches_target "$REPO_ROOT/skills/${link##*/}" opencode || continue
  shared=$((shared + 1))
done
for link in "$HOME_OCE/.config/opencode/skills"/*; do
  [[ -L "$link" ]] || continue
  [[ ! -e "$HOME_OCE/.agents/skills/${link##*/}" ]] ||
    fail "opencode linked ${link##*/} although codex has it"
done
got="$(count_links "$HOME_OCE/.config/opencode/skills")"
want=$((OPENCODE_EXPECTED - shared))
[[ "$got" -eq "$want" ]] || fail "opencode with codex --env=chat: expected $want links, got $got"
oc_dry="$(HOME="$(mktemp -d)" "$INSTALL" --target=all --dry-run 2>&1)"
[[ "$(grep -c '^\[dry-run\] link .*/\.config/opencode/skills/' <<<"$oc_dry")" -eq "$OPENCODE_ONLY_EXPECTED" ]] ||
  fail "dry-run --target=all planned opencode links that codex shares"
if grep -q '^  linked .*\.config/opencode/skills/' <<<"$oc_dry"; then
  fail "dry-run reported a link twice"
fi
grep -q 'shared .*/\.config/opencode/skills/' <<<"$oc_dry" ||
  fail "dry-run --target=all did not report the shared skills"
pass "opencode links what codex lacks, and dry-run plans the shared state"

# 6h2. each planned write uses one normalized dry-run line.
dry_action_lines="$(grep '^\[dry-run\]' <<<"$oc_dry")"
if grep -Ev '^\[dry-run\] (link|write|remove) .+$' <<<"$dry_action_lines" >/dev/null; then
  fail "dry-run emitted a non-normalized action line"
fi
if grep -Eq '^  (linked|removed|updated|agent) ' <<<"$oc_dry"; then
  fail "dry-run emitted a second write status line"
fi
[[ "$(grep -c '^\[dry-run\] write .*/\.codex/agents/.*\.toml$' <<<"$oc_dry")" -eq 2 ]] ||
  fail "dry-run did not report each agent TOML write once"

# 6i. An earlier opencode install skipped the skills it read from
#     ~/.claude/skills. The claude migration removes those links, so it hands
#     each skill to an installed opencode, except those codex shares (#567).
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
pass "claude migration hands removed skills to an installed opencode"

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
: >"$foreign_prompt_src"
ln -s "$foreign_prompt_src" "$legacy_prompts/foreign-prompt.md"
HOME="$HOME_CX" "$INSTALL" --target=codex >/dev/null
[[ ! -L "$legacy_prompts/$first_command.md" ]] || fail "deprecated codex prompt for $first_command not migrated"
[[ -L "$legacy_prompts/foreign-prompt.md" ]] || fail "codex prompt cleanup removed a foreign symlink"
pass "codex install cleans the deprecated prompts dir"

# 6d. codex links into ~/.agents/skills (#565) and migrates our links out of the
#     deprecated ~/.codex/skills, still-valid and dangling ones alike, whatever
#     --category says; foreign entries there survive, and a dry-run keeps all.
HOME_CXS="$(mktemp -d)"
legacy_skills="$HOME_CXS/.codex/skills"
mkdir -p "$legacy_skills/hand-made"
ln -s "$REPO_ROOT/skills/documentation" "$legacy_skills/documentation"
ln -s "$REPO_ROOT/skills/architecture" "$legacy_skills/architecture"
ln -s "$REPO_ROOT/skills/removed-skill" "$legacy_skills/removed-skill"
foreign_codex_skill="$(mktemp -d)/foreign-skill"
mkdir "$foreign_codex_skill"
ln -s "$foreign_codex_skill" "$legacy_skills/foreign-skill"
HOME="$HOME_CXS" "$INSTALL" --target=codex --category=communication --dry-run >/dev/null
[[ -L "$legacy_skills/documentation" ]] || fail "dry-run migrated a ~/.codex/skills link"
HOME="$HOME_CXS" "$INSTALL" --target=codex --category=communication >/dev/null
for name in documentation architecture removed-skill; do
  [[ ! -L "$legacy_skills/$name" ]] || fail "our ~/.codex/skills/$name link was not migrated"
done
[[ -L "$legacy_skills/foreign-skill" ]] || fail "codex migration removed a foreign symlink"
[[ -d "$legacy_skills/hand-made" ]] || fail "codex migration removed a foreign directory"
[[ -L "$HOME_CXS/.agents/skills/documentation" ]] || fail "codex did not link into ~/.agents/skills"
ln -s "$REPO_ROOT/skills/documentation" "$legacy_skills/documentation"
HOME="$HOME_CXS" "$INSTALL" --target=codex --category=communication --uninstall >/dev/null
[[ ! -L "$legacy_skills/documentation" ]] || fail "codex uninstall left our ~/.codex/skills link"
[[ ! -e "$HOME_CXS/.agents/skills/documentation" ]] || fail "codex uninstall left ~/.agents/skills link"
pass "codex links into ~/.agents/skills and migrates out of ~/.codex/skills"

# 6e. other tools write to ~/.agents/skills too: a name already taken there is
#     warned about and left alone, never overwritten (#565).
HOME_COL="$(mktemp -d)"
mkdir -p "$HOME_COL/.agents/skills/documentation"
printf 'theirs\n' >"$HOME_COL/.agents/skills/documentation/SKILL.md"
foreign_tldr="$(mktemp -d)/tldr"
mkdir "$foreign_tldr"
ln -s "$foreign_tldr" "$HOME_COL/.agents/skills/tldr"
col_err="$(HOME="$HOME_COL" "$INSTALL" --target=codex --category=communication 2>&1 >/dev/null)"
grep -Fxq 'theirs' "$HOME_COL/.agents/skills/documentation/SKILL.md" ||
  fail "codex install overwrote a foreign skill in ~/.agents/skills"
[[ "$(readlink "$HOME_COL/.agents/skills/tldr")" == "$foreign_tldr" ]] ||
  fail "codex install replaced a foreign symlink in ~/.agents/skills"
grep -q 'WARN.*agents/skills/documentation' <<<"$col_err" ||
  fail "no warning for the name collision on documentation"
grep -q 'WARN.*agents/skills/tldr' <<<"$col_err" ||
  fail "no warning for the name collision on tldr"
[[ -L "$HOME_COL/.agents/skills/communication-analysis" ]] ||
  fail "a collision stopped the remaining codex links"
pass "name collisions in ~/.agents/skills warn and keep the foreign entry"

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
CHAT_EXPECTED=$(($(skill_count chat opencode) + $(command_count chat opencode)))
CODING_EXPECTED=$(($(skill_count coding opencode) + $(command_count coding opencode)))
[[ "$CHAT_EXPECTED" -ge 1 ]] || fail "no chat skills detected"
[[ "$CHAT_EXPECTED" -lt "$OPENCODE_EXPECTED" ]] || fail "chat subset is not smaller than all"
HOME_CHAT="$(mktemp -d)"
HOME="$HOME_CHAT" "$INSTALL" --target=opencode --env=chat >/dev/null
got="$(count_links "$HOME_CHAT/.config/opencode/skills")"
[[ "$got" -eq "$CHAT_EXPECTED" ]] || fail "env=chat: expected $CHAT_EXPECTED links, got $got"
pass "env=chat links only the $CHAT_EXPECTED chat skills"

# 8. --env=coding links only the coding subset.
HOME_CODE="$(mktemp -d)"
HOME="$HOME_CODE" "$INSTALL" --target=opencode --env=coding >/dev/null
got="$(count_links "$HOME_CODE/.config/opencode/skills")"
[[ "$got" -eq "$CODING_EXPECTED" ]] || fail "env=coding: expected $CODING_EXPECTED links, got $got"
pass "env=coding links only the $CODING_EXPECTED coding skills"

# 9. coding + chat cover at least every skill (skills in both are counted twice).
[[ $((CODING_EXPECTED + CHAT_EXPECTED)) -ge "$OPENCODE_EXPECTED" ]] ||
  fail "coding ($CODING_EXPECTED) + chat ($CHAT_EXPECTED) < all ($OPENCODE_EXPECTED)"
pass "coding + chat subsets cover all skills"

# 10. dry-run with a filter creates nothing.
HOME_DF="$(mktemp -d)"
HOME="$HOME_DF" "$INSTALL" --target=opencode --env=chat --dry-run >/dev/null
[[ ! -d "$HOME_DF/.config/opencode" ]] || fail "dry-run --env=chat created $HOME_DF/.config/opencode"
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
    skill_is_nested_member "$d" && continue
    skill_matches_target "$d" "$target" || continue
    local cat
    cat="$(grep -m1 '^category:' "$d/SKILL.md" 2>/dev/null | sed 's/^category://')"
    cat="${cat//[[:space:]]/}"
    [[ -n "$cat" ]] && [[ ",$want," == *",$cat,"* ]] && n=$((n + 1))
  done
  echo "$n"
}
ARCH_EXPECTED="$(category_count architecture opencode)"
[[ "$ARCH_EXPECTED" -ge 1 ]] || fail "no architecture skills detected"
[[ "$ARCH_EXPECTED" -lt "$OPENCODE_EXPECTED" ]] || fail "architecture subset is not smaller than all"
HOME_CAT="$(mktemp -d)"
HOME="$HOME_CAT" "$INSTALL" --target=opencode --category=architecture >/dev/null
got="$(count_links "$HOME_CAT/.config/opencode/skills")"
[[ "$got" -eq "$ARCH_EXPECTED" ]] || fail "category=architecture: expected $ARCH_EXPECTED links, got $got"
pass "category=architecture links only the $ARCH_EXPECTED architecture skills"

# 13. a comma-separated --category list links the union of both subsets.
MULTI_EXPECTED="$(category_count architecture,refactoring opencode)"
HOME_MULTI="$(mktemp -d)"
HOME="$HOME_MULTI" "$INSTALL" --target=opencode --category=architecture,refactoring >/dev/null
got="$(count_links "$HOME_MULTI/.config/opencode/skills")"
[[ "$got" -eq "$MULTI_EXPECTED" ]] || fail "category list: expected $MULTI_EXPECTED links, got $got"
pass "category=architecture,refactoring links $MULTI_EXPECTED skills"

# 14. an invalid --category value is rejected.
if HOME="$(mktemp -d)" "$INSTALL" --target=claude --category=bogus >/dev/null 2>&1; then
  fail "invalid --category=bogus was accepted"
fi
pass "invalid --category is rejected"

# 14a. an empty --category value reaches validation on Bash 3.2 with nounset.
if empty_category_output="$(HOME="$(mktemp -d)" "$INSTALL" --target=claude --category= 2>&1)"; then
  fail "empty --category was accepted"
else
  empty_category_status=$?
fi
[[ "$empty_category_status" -eq 2 ]] || fail "empty --category did not exit 2"
[[ "$empty_category_output" == *"invalid --category= (expected one of:"* ]] ||
  fail "empty --category did not reach validation"
echo "ok: empty --category is rejected before Bash 3.2 nounset array expansion"

# 18. a category without a router leaves config.toml alone (communication
#     ships no router, so nothing managed is written to config.toml).
HOME_NOMCP="$(mktemp -d)"
HOME="$HOME_NOMCP" "$INSTALL" --target=codex --category=communication >/dev/null
[[ ! -f "$HOME_NOMCP/.codex/config.toml" ]] ||
  fail "category=communication created config.toml"
pass "category without a router leaves config.toml alone"

# 21. unbalanced markers (hand-deleted end markers) leave the file untouched.
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
pass "unbalanced markers leave config.toml untouched"

# 21a. codex install disables every nested router member via [[skills.config]].
#      architecture is routed and has the most members, so it exercises the
#      block best.
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
pass "codex install disables nested router members"

# 21b. a routed category writes only the override block — the installer no
#      longer registers MCP servers at all — and reinstalling is byte-identical.
HOME_OV2="$(mktemp -d)"
HOME="$HOME_OV2" "$INSTALL" --target=codex --category=ai-ml >/dev/null
CONFIG_OV2="$HOME_OV2/.codex/config.toml"
[[ -f "$CONFIG_OV2" ]] || fail "routed category=ai-ml created no config.toml"
grep -q '^\[mcp_servers\.' "$CONFIG_OV2" &&
  fail "install wrote mcp_servers into config.toml"
before="$(cat "$CONFIG_OV2")"
HOME="$HOME_OV2" "$INSTALL" --target=codex --category=ai-ml >/dev/null
[[ "$(cat "$CONFIG_OV2")" == "$before" ]] || fail "override registration is not idempotent"
pass "override-only config is written and idempotent"

# 21c. uninstall removes the override block but keeps foreign config.
printf '\n[foreign]\nkeep = true\n' >>"$CONFIG_OV2"
HOME="$HOME_OV2" "$INSTALL" --target=codex --category=ai-ml --uninstall >/dev/null
grep -Fxq '[foreign]' "$CONFIG_OV2" || fail "override uninstall dropped foreign config"
grep -q 'skills\.config\|routed-member skill overrides' "$CONFIG_OV2" &&
  fail "override uninstall left our block behind"
pass "override uninstall removes only our block"

# 21c2. an unchanged override block is left alone: a reinstall reports "ok"
#       without rewriting the file, and a dry-run plans no removal.
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
grep -Fq "[dry-run] remove $CONFIG_OV3" <<<"$ov_dry" &&
  fail "dry-run planned removing an override block it would keep"
pass "unchanged override block is neither rewritten nor planned for removal"

# 21c2a. routed-member and guard blocks retain their order and inode on rerun.
HOME_BLOCK_ORDER="$(mktemp -d)"
HOME="$HOME_BLOCK_ORDER" "$INSTALL" --target=codex --category=architecture --merge-guard >/dev/null
CONFIG_BLOCK_ORDER="$HOME_BLOCK_ORDER/.codex/config.toml"
block_order() {
  awk '
    /^# >>> agents routed-member skill overrides/ { print "routed" }
    /^# >>> agents PR merge guard/ { print "merge" }
  ' "$1"
}
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
echo "ok: managed blocks retain their content, inode, and order"

# 21c3. a narrower --category re-run keeps the overrides of routers still
#       installed (#562): the full install links the architecture and ai-ml
#       routers, a communication-only re-run leaves those links in place, so
#       their nested members must stay disabled.
HOME_OV4="$(mktemp -d)"
HOME="$HOME_OV4" "$INSTALL" --target=codex >/dev/null
CONFIG_OV4="$HOME_OV4/.codex/config.toml"
before="$(cat "$CONFIG_OV4")"
grep -q 'routed-member skill overrides' <<<"$before" ||
  fail "full codex install wrote no override block"
HOME="$HOME_OV4" "$INSTALL" --target=codex --category=communication >/dev/null
[[ "$(cat "$CONFIG_OV4")" == "$before" ]] ||
  fail "narrower --category re-run changed the override block of installed routers"
pass "narrower --category re-run keeps overrides of installed routers"

# 21c4. Reinstalling routed-member and merge-guard blocks leaves their order
#       and config inode unchanged.
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
pass "routed-member and merge-guard blocks keep their order and inode"

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

# Install path: cleanup runs even for a category that never shipped a server.
HOME_LEGACY="$(mktemp -d)"
make_legacy_mcp_home "$HOME_LEGACY"
CONFIG_LEGACY="$HOME_LEGACY/.codex/config.toml"
HOME="$HOME_LEGACY" "$INSTALL" --target=codex --category=ai-ml >/dev/null
assert_legacy_mcp_gone "$CONFIG_LEGACY" "install"
[[ -d "$HOME_LEGACY/.codex/agents-mcp-runtime" ]] &&
  fail "install left the legacy MCP runtime venv behind"
"$PYTHON" - "$CONFIG_LEGACY" <<'PY' || fail "legacy cleanup left invalid TOML"
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
[[ -d "$HOME_LEGACY_UN/.codex/agents-mcp-runtime" ]] &&
  fail "uninstall left the legacy MCP runtime venv behind"
pass "uninstall strips legacy MCP blocks; dry-run only reports them"

# 22. codex install converts plugin subagents to valid custom-agent TOML.
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
pass "codex install converts subagents to valid agent TOML"

# 23. re-running leaves the agent files identical; foreign files survive.
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
pass "agent conversion is idempotent and preserves foreign files"

# 24. uninstall removes generated agents only; foreign files stay.
HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture --uninstall >/dev/null 2>&1
[[ ! -f "$AGENTS_DIR/coupling-analyst.toml" ]] ||
  fail "uninstall left a generated agent file"
[[ -f "$AGENTS_DIR/cohesion-analyst.toml" ]] ||
  fail "uninstall removed a foreign agent file"
pass "uninstall removes only generated agent files"

# 25. a category without agents creates no agents directory.
HOME_NOAG="$(mktemp -d)"
HOME="$HOME_NOAG" "$INSTALL" --target=codex --category=workflow >/dev/null
[[ ! -d "$HOME_NOAG/.codex/agents" ]] ||
  fail "category=workflow created an agents directory"
pass "category without subagents leaves agents directory alone"

# 25b. a generated agent whose source is gone (renamed or deleted subagent) is
#      pruned on the next codex run, whatever --category says; foreign files
#      and generated agents whose source still exists stay.
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
pass "stale generated agent files are pruned, foreign and live ones kept"

# 36. A routed category links only its router at top level; the auto members
#     ride nested under the router's members/ dir (readable, not registered),
#     and none of them leak into the skills directory.
HOME_ROUTED="$(mktemp -d)"
HOME="$HOME_ROUTED" "$INSTALL" --target=opencode --category=architecture >/dev/null
ROUTED_SKILLS="$HOME_ROUTED/.config/opencode/skills"
[[ -L "$ROUTED_SKILLS/architecture" ]] || fail "router 'architecture' not linked"
[[ -f "$ROUTED_SKILLS/architecture/SKILL.md" ]] || fail "router SKILL.md not readable"
[[ "$(count_links "$ROUTED_SKILLS")" -eq 1 ]] ||
  fail "routed category linked more than the router at top level"
# A representative member resolves through the router's members/ dir ...
[[ -f "$ROUTED_SKILLS/architecture/members/coupling-cohesion/SKILL.md" ]] ||
  fail "nested member coupling-cohesion not readable via the router"
# ... but is never registered as its own top-level skill.
for member in c4-modeling coupling-cohesion ddd; do
  [[ ! -e "$ROUTED_SKILLS/$member" ]] ||
    fail "routed member $member leaked into the skills directory"
done
HOME="$HOME_ROUTED" "$INSTALL" --target=opencode --category=architecture --uninstall >/dev/null
[[ ! -e "$ROUTED_SKILLS/architecture" ]] || fail "uninstall left the router behind"
pass "routed category registers only its router; members ride nested"

# 36a. Migration from a pre-router install: members used to be linked flat at
#      top level. Those links still resolve, so the dangling-link prune cannot
#      catch them — install must unlink them explicitly, or the members keep
#      registering alongside the router. Foreign entries must survive.
HOME_MIG="$(mktemp -d)"
MIG_SKILLS="$HOME_MIG/.config/opencode/skills"
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
HOME="$HOME_MIG" "$INSTALL" --target=opencode --category=architecture >/dev/null
while IFS= read -r name; do
  [[ -n "$name" ]] || continue
  [[ ! -e "$MIG_SKILLS/$name" ]] ||
    fail "pre-router flat link for $name survived the upgrade"
done <<<"$mig_members"
[[ -L "$MIG_SKILLS/architecture" ]] || fail "migration did not link the router"
[[ -L "$MIG_SKILLS/foreign-skill" ]] || fail "migration removed a foreign symlink"
# ... and --uninstall clears the flat links too, not just the router.
HOME="$HOME_MIG" "$INSTALL" --target=opencode --category=architecture >/dev/null
while IFS= read -r name; do
  [[ -n "$name" ]] || continue
  ln -s "$REPO_ROOT/skills/$name" "$MIG_SKILLS/$name"
done <<<"$mig_members"
HOME="$HOME_MIG" "$INSTALL" --target=opencode --category=architecture --uninstall >/dev/null
while IFS= read -r name; do
  [[ -n "$name" ]] || continue
  [[ ! -e "$MIG_SKILLS/$name" ]] || fail "uninstall left the pre-router flat link for $name"
done <<<"$mig_members"
[[ -L "$MIG_SKILLS/foreign-skill" ]] || fail "uninstall removed a foreign symlink"
pass "pre-router flat member links are cleaned up on install and uninstall"

# 37. A `targets:` skill installs only for the agents it lists. No shipped skill
#     currently uses the field, so exercise it with a temporary fixture skill
#     that opts out of opencode: it must reach codex only — and a stale link
#     in the opencode skills dir is cleaned up by the next install.
TGT_FIXTURE="$REPO_ROOT/skills/zz-targets-fixture"
rm_tgt_fixture() { rm -rf "$TGT_FIXTURE"; }
trap rm_tgt_fixture EXIT
mkdir -p "$TGT_FIXTURE/scripts"
cat >"$TGT_FIXTURE/SKILL.md" <<'FIXTURE'
---
name: zz-targets-fixture
description: Temporary fixture used by test_install.sh to exercise the targets field.
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
rm_tgt_fixture
trap - EXIT
pass "targets: skips excluded agents and prunes a stale link"

# 38. A dangling symlink left by a skill the repo no longer ships is pruned;
#     foreign and still-valid links are left alone.
HOME_STALE="$(mktemp -d)"
HOME="$HOME_STALE" "$INSTALL" --target=opencode --category=communication >/dev/null
STALE_SKILLS="$HOME_STALE/.config/opencode/skills"
ln -s "$REPO_ROOT/skills/removed-skill" "$STALE_SKILLS/removed-skill"
foreign_dangling="$(mktemp -d)/gone"
ln -s "$foreign_dangling" "$STALE_SKILLS/foreign-dangling"
HOME="$HOME_STALE" "$INSTALL" --target=opencode --category=communication >/dev/null
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
diff -q "$HOME_INS/claude-before.md" "$HOME_INS/.claude/CLAUDE.md" >/dev/null ||
  fail "instructions written without --instructions"
[[ ! -e "$HOME_INS/.agents/instructions" ]] || fail "instruction payloads written without --instructions"
[[ ! -e "$HOME_INS/.claude/settings.json" ]] || fail "Claude hook written without --instructions"
pass "instructions are not touched without --instructions"

# 40. With the flag the block lands, hand-written content survives, and a
#     second run is a no-op (idempotent).
HOME="$HOME_INS" "$INSTALL" --target=claude --category=communication --instructions >/dev/null
CLAUDE_MD="$HOME_INS/.claude/CLAUDE.md"
grep -q '^my own notes$' "$CLAUDE_MD" || fail "hand-written line lost"
grep -q '^@RTK.md$' "$CLAUDE_MD" || fail "@-import lost"
grep -q 'agents instructions (managed by install.sh' "$CLAUDE_MD" || fail "begin marker missing"
grep -q '<!-- <<< agents instructions <<< -->' "$CLAUDE_MD" || fail "end marker missing"
! grep -q 'Use uv for Python package development' "$CLAUDE_MD" ||
  fail "path-scoped Python fragment stayed in Claude's always-on block"
PYTHON_RULE="$HOME_INS/.claude/rules/agents-30-python.md"
[[ -f "$PYTHON_RULE" ]] || fail "path-scoped Python rule was not written"
grep -q '"\*\*/\*.py"' "$PYTHON_RULE" || fail "Python rule lacks its quoted paths glob"
grep -q 'New project baseline' "$PYTHON_RULE" || fail "Python rule has no baseline"
[[ -f "$HOME_INS/.agents/instructions/30-python.md" ]] || fail "Python baseline payload missing"
[[ -f "$HOME_INS/.agents/instructions/70-code-review-conventions.md" ]] || fail "code review payload missing"
[[ -f "$HOME_INS/.agents/instructions/80-agent-pipelines.md" ]] || fail "agent pipeline payload missing"
[[ -f "$HOME_INS/.agents/instructions/85-agent-scripts.md" ]] || fail "agent scripts payload missing"
grep -Fq '.agents/instructions/70-code-review-conventions.md' "$CLAUDE_MD" ||
  fail "Claude block lacks the code review pointer"
[[ -f "$HOME_INS/.agents/instructions/python_init_context.py" ]] || fail "Python hook command missing"
"$PYTHON" - "$HOME_INS/.claude/settings.json" <<'PY' || fail "Claude uv-init hook missing"
import json, sys
settings = json.load(open(sys.argv[1], encoding="utf-8"))
handlers = [h for group in settings["hooks"]["PreToolUse"] for h in group["hooks"]]
entry = next(h for h in handlers if h.get("if") == "Bash(uv init*)")
assert "python_init_context.py" in entry["command"]
PY
hook_output="$(printf '%s' '{"tool_name":"Bash","tool_input":{"command":"uv init --package demo"}}' |
  (cd /tmp && HOME="$HOME_INS" "$PYTHON" "$HOME_INS/.agents/instructions/python_init_context.py"))"
grep -q 'New project baseline' <<<"$hook_output" || fail "installed uv-init hook did not inject the Python baseline"
cp "$CLAUDE_MD" "$HOME_INS/claude-once.md"
cp "$HOME_INS/.claude/settings.json" "$HOME_INS/settings-once.json"
HOME="$HOME_INS" "$INSTALL" --target=claude --category=communication --instructions >/dev/null
diff -q "$HOME_INS/claude-once.md" "$CLAUDE_MD" >/dev/null ||
  fail "second --instructions run changed the file"
diff -q "$HOME_INS/settings-once.json" "$HOME_INS/.claude/settings.json" >/dev/null ||
  fail "second --instructions run changed Claude settings"
pass "instructions block installs once and is idempotent"

# 41. --uninstall strips only our block, restoring the file byte for byte.
HOME="$HOME_INS" "$INSTALL" --target=claude --category=communication --instructions --uninstall >/dev/null
diff -q "$HOME_INS/claude-before.md" "$CLAUDE_MD" >/dev/null ||
  fail "uninstall did not restore the original instruction file"
[[ ! -e "$HOME_INS/.agents/instructions/30-python.md" ]] || fail "uninstall left the Python payload"
[[ ! -e "$HOME_INS/.agents/instructions/python_init_context.py" ]] || fail "uninstall left the Python hook command"
! grep -q python_init_context.py "$HOME_INS/.claude/settings.json" ||
  fail "uninstall left the Claude uv-init hook"
pass "instructions uninstall removes only the managed block"

# 42. codex and opencode each get their own file created from nothing
#     (opencode reads ~/.claude/CLAUDE.md only as a fallback, V2 not at all),
#     and --uninstall strips the block from both.
HOME_INS2="$(mktemp -d)"
HOME="$HOME_INS2" "$INSTALL" --target=all --category=communication --instructions >/dev/null
for f in .codex/AGENTS.md .config/opencode/AGENTS.md; do
  [[ -f "$HOME_INS2/$f" ]] || fail "$f was not created"
  grep -q 'For Python work, read' "$HOME_INS2/$f" ||
    fail "$f has no Python baseline pointer"
  ! grep -q 'Use uv for Python package development' "$HOME_INS2/$f" ||
    fail "$f loaded the Python baseline inline"
done
grep -q 'Use uv for Python package development' "$HOME_INS2/.agents/instructions/30-python.md" ||
  fail "Codex/opencode Python pointer has no installed target"
HOME="$HOME_INS2" "$INSTALL" --target=opencode --category=communication --instructions --uninstall >/dev/null
! grep -q 'agents instructions' "$HOME_INS2/.config/opencode/AGENTS.md" ||
  fail "opencode uninstall left the instructions block"
[[ -f "$HOME_INS2/.agents/instructions/80-agent-pipelines.md" ]] ||
  fail "target-specific uninstall removed a payload still used by codex and claude"
pass "instructions create codex's and opencode's own files"

# 42a. A foreign file at a payload path is never overwritten, and the block
#      leaves out the pointer to it.
HOME_INS5="$(mktemp -d)"
mkdir -p "$HOME_INS5/.agents/instructions"
printf 'mine\n' >"$HOME_INS5/.agents/instructions/85-agent-scripts.md"
HOME="$HOME_INS5" "$INSTALL" --target=codex --category=communication --instructions >/dev/null 2>&1
[[ "$(cat "$HOME_INS5/.agents/instructions/85-agent-scripts.md")" == mine ]] ||
  fail "install overwrote a foreign payload file"
! grep -q '85-agent-scripts.md' "$HOME_INS5/.codex/AGENTS.md" ||
  fail "block points at a foreign payload file"
grep -q '70-code-review-conventions.md' "$HOME_INS5/.codex/AGENTS.md" ||
  fail "block lost the pointer to an owned payload"
HOME="$HOME_INS5" "$INSTALL" --target=codex --category=communication --instructions --uninstall >/dev/null 2>&1
[[ -f "$HOME_INS5/.agents/instructions/85-agent-scripts.md" ]] || fail "uninstall removed a foreign payload file"
[[ ! -e "$HOME_INS5/.agents/instructions/70-code-review-conventions.md" ]] ||
  fail "uninstall left an unreferenced owned payload"
pass "foreign payload files are left alone and not pointed at"

# 43. Unbalanced markers (a hand edit) leave the file completely alone, and
#     --dry-run never writes.
HOME_INS3="$(mktemp -d)"
mkdir -p "$HOME_INS3/.claude"
printf 'notes\n\n<!-- >>> agents instructions (managed by install.sh, do not edit) >>> -->\nstray\n' \
  >"$HOME_INS3/.claude/CLAUDE.md"
cp "$HOME_INS3/.claude/CLAUDE.md" "$HOME_INS3/unbalanced-before.md"
HOME="$HOME_INS3" "$INSTALL" --target=claude --category=communication --instructions >/dev/null 2>&1
diff -q "$HOME_INS3/unbalanced-before.md" "$HOME_INS3/.claude/CLAUDE.md" >/dev/null ||
  fail "unbalanced markers did not protect the file"
HOME_INS4="$(mktemp -d)"
ins_dry_output="$(HOME="$HOME_INS4" "$INSTALL" --target=codex --category=communication --instructions --dry-run 2>&1)"
[[ ! -e "$HOME_INS4/.codex/AGENTS.md" ]] || fail "dry-run wrote an instruction file"
grep -Fq "[dry-run] write $HOME_INS4/.codex/AGENTS.md" <<<"$ins_dry_output" ||
  fail "dry-run did not report the instruction block write"
pass "unbalanced markers and dry-run never write instruction files"

# 44. A fragment with `paths:` leaves Claude's block for a path-scoped rule
#     under ~/.claude/rules/ (codex and opencode keep R inline and use the
#     Python pointer), a foreign rule file is never touched, and --uninstall
#     removes only ours.
HOME_RULE_DRY="$(mktemp -d)"
RULE_DRY_PATH="$HOME_RULE_DRY/.claude/rules/agents-40-r.md"
rule_dry_output="$(HOME="$HOME_RULE_DRY" "$INSTALL" --target=all --category=communication --instructions --dry-run 2>&1)"
[[ "$(grep -Fc "[dry-run] write $RULE_DRY_PATH" <<<"$rule_dry_output")" -eq 1 ]] ||
  fail "dry-run did not report the Claude rule write exactly once"
[[ ! -d "$HOME_RULE_DRY/.claude/rules" ]] ||
  fail "dry-run created the Claude rules directory"

HOME_RULES="$(mktemp -d)"
mkdir -p "$HOME_RULES/.claude/rules"
printf 'mine\n' >"$HOME_RULES/.claude/rules/own.md"
HOME="$HOME_RULES" "$INSTALL" --target=all --category=communication --instructions >/dev/null
R_RULE="$HOME_RULES/.claude/rules/agents-40-r.md"
[[ -f "$R_RULE" ]] || fail "path-scoped R rule was not written"
grep -qxF '  - "**/*.R"' "$R_RULE" || fail "R rule lacks its quoted paths glob"
grep -q 'Namespace' "$R_RULE" || fail "R rule has no fragment body"
! grep -q 'Namespace' "$HOME_RULES/.claude/CLAUDE.md" ||
  fail "path-scoped fragment still inside Claude's block"
for f in .codex/AGENTS.md .config/opencode/AGENTS.md; do
  grep -q 'Namespace' "$HOME_RULES/$f" || fail "$f lost the path-scoped fragment"
  grep -q 'For Python work, read' "$HOME_RULES/$f" || fail "$f lost the Python pointer"
  ! grep -q 'Use uv for Python package development' "$HOME_RULES/$f" ||
    fail "$f loaded the Python baseline inline"
done
rule_content_before="$(cat "$R_RULE")"
rule_inode_before="$(file_inode "$R_RULE")"
rule_output="$(HOME="$HOME_RULES" "$INSTALL" --target=all --category=communication --instructions 2>&1)"
[[ "$(cat "$R_RULE")" == "$rule_content_before" ]] ||
  fail "reinstall changed an unchanged Claude rule"
[[ "$(file_inode "$R_RULE")" == "$rule_inode_before" ]] ||
  fail "reinstall rewrote an unchanged Claude rule"
grep -q '  ok .*agents-40-r.md' <<<"$rule_output" ||
  fail "reinstall did not report the unchanged Claude rule as ok"
HOME="$HOME_RULES" "$INSTALL" --target=claude --category=communication --instructions --uninstall >/dev/null 2>&1
[[ ! -e "$R_RULE" ]] || fail "uninstall left the managed R rule"
[[ -f "$HOME_RULES/.agents/instructions/80-agent-pipelines.md" ]] ||
  fail "Claude uninstall removed a payload still used by codex and opencode"
[[ -f "$HOME_RULES/.claude/rules/own.md" ]] || fail "uninstall removed a foreign rule file"
pass "paths: fragments become path-scoped Claude rules only"

# 45. --merge-guard puts the PR merge guard into each agent's user-level config
#     (Codex [hooks] block, opencode plugin link; Claude only gets the plugin
#     command printed), keeps foreign settings, is idempotent, and --uninstall
#     restores the files.
HOME_MG="$(mktemp -d)"
mkdir -p "$HOME_MG/.claude" "$HOME_MG/.codex"
printf '{"model": "opus", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]}}\n' \
  >"$HOME_MG/.claude/settings.json"
cp "$HOME_MG/.claude/settings.json" "$HOME_MG/claude-before.json"
printf 'model = "o3"\n' >"$HOME_MG/.codex/config.toml"
cp "$HOME_MG/.codex/config.toml" "$HOME_MG/codex-before.toml"
HOME="$HOME_MG" "$INSTALL" --target=all --category=communication >/dev/null
grep -q pr_merge_guard "$HOME_MG/.claude/settings.json" "$HOME_MG/.codex/config.toml" &&
  fail "merge guard installed without --merge-guard"
mg_output="$(HOME="$HOME_MG" "$INSTALL" --target=all --category=communication --merge-guard)"
grep -q 'claude plugin install merge-guard@fabiandistler-agents' <<<"$mg_output" ||
  fail "--merge-guard did not point claude at the merge-guard plugin"
diff -q "$HOME_MG/claude-before.json" "$HOME_MG/.claude/settings.json" >/dev/null ||
  fail "--merge-guard wrote into ~/.claude/settings.json"
"$PYTHON" - "$HOME_MG" <<'PY' || fail "merge guard entries missing or foreign settings lost"
import sys, tomllib
home = sys.argv[1]
codex = tomllib.load(open(f"{home}/.codex/config.toml", "rb"))
assert codex["model"] == "o3"
assert "--harness codex" in codex["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
PY
[[ -L "$HOME_MG/.config/opencode/plugins/pr-merge-guard.js" ]] || fail "opencode plugin not linked"
cp "$HOME_MG/.codex/config.toml" "$HOME_MG/codex-once.toml"
HOME="$HOME_MG" "$INSTALL" --target=all --category=communication --merge-guard >/dev/null
diff -q "$HOME_MG/codex-once.toml" "$HOME_MG/.codex/config.toml" >/dev/null ||
  fail "second --merge-guard run changed config.toml"
HOME="$HOME_MG" "$INSTALL" --target=all --category=communication --merge-guard --uninstall >/dev/null
diff -q "$HOME_MG/claude-before.json" "$HOME_MG/.claude/settings.json" >/dev/null ||
  fail "uninstall changed a settings.json without our entry"
diff -q "$HOME_MG/codex-before.toml" "$HOME_MG/.codex/config.toml" >/dev/null ||
  fail "uninstall did not restore config.toml"
[[ ! -e "$HOME_MG/.config/opencode/plugins/pr-merge-guard.js" ]] || fail "uninstall left the plugin"
pass "--merge-guard installs per agent, idempotently, and uninstalls cleanly"

# 46. --secret-guard installs next to --merge-guard: two Codex hook entries in
#     one valid config.toml, its own opencode link and plugin hint, idempotent,
#     and --secret-guard --uninstall leaves the merge guard in place.
HOME_SG="$(mktemp -d)"
mkdir -p "$HOME_SG/.codex"
printf 'model = "o3"\n' >"$HOME_SG/.codex/config.toml"
HOME="$HOME_SG" "$INSTALL" --target=all --category=communication --merge-guard >/dev/null
cp "$HOME_SG/.codex/config.toml" "$HOME_SG/merge-only.toml"
sg_output="$(HOME="$HOME_SG" "$INSTALL" --target=all --category=communication \
  --merge-guard --secret-guard)"
grep -q 'claude plugin install secret-guard@fabiandistler-agents' <<<"$sg_output" ||
  fail "--secret-guard did not point claude at the secret-guard plugin"
"$PYTHON" - "$HOME_SG" <<'PY' || fail "secret guard entry missing next to the merge guard"
import sys, tomllib
codex = tomllib.load(open(f"{sys.argv[1]}/.codex/config.toml", "rb"))
commands = [e["hooks"][0]["command"] for e in codex["hooks"]["PreToolUse"]]
assert [c.split("/")[-1] for c in commands] == [
    'pr_merge_guard.py" --harness codex', 'secret_read_guard.py" --harness codex'
], commands
PY
[[ -L "$HOME_SG/.config/opencode/plugins/secret-read-guard.js" ]] ||
  fail "opencode secret guard plugin not linked"
cp "$HOME_SG/.codex/config.toml" "$HOME_SG/both.toml"
HOME="$HOME_SG" "$INSTALL" --target=all --category=communication --merge-guard --secret-guard >/dev/null
diff -q "$HOME_SG/both.toml" "$HOME_SG/.codex/config.toml" >/dev/null ||
  fail "second --secret-guard run changed config.toml"
HOME="$HOME_SG" "$INSTALL" --target=all --category=communication --secret-guard --uninstall >/dev/null
diff -q "$HOME_SG/merge-only.toml" "$HOME_SG/.codex/config.toml" >/dev/null ||
  fail "--secret-guard --uninstall did not leave just the merge guard"
[[ ! -e "$HOME_SG/.config/opencode/plugins/secret-read-guard.js" ]] ||
  fail "uninstall left the secret guard plugin"
[[ -L "$HOME_SG/.config/opencode/plugins/pr-merge-guard.js" ]] ||
  fail "--secret-guard --uninstall removed the merge guard plugin"
pass "--secret-guard installs next to the merge guard and uninstalls on its own"

# --check: drift report for the managed state.
run_check_tests

# --update: saved install state and replay.
run_update_tests

# --target=detected: resolve targets from installed agents.
run_detected_tests

# --git-hook: per-clone post-merge/post-rewrite hooks.
run_git_hook_tests
run_git_hook_worktree_tests

# OpenCode subagents rendered from the plugin agents.
run_opencode_agent_tests

# OpenCode command skills via slash metadata.
run_command_skill_tests

# --uninstall: keeps the saved install state in step with what it removed.
run_uninstall_state_tests

echo "all install.sh tests passed"
