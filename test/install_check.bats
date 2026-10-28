#!/usr/bin/env bats
# install.sh --check: the read-only drift report for the managed state.

load install_helper

setup() {
  install_setup
}

@test "--check reports missing managed files as TSV without writing" {
  check_home="$(mktemp -d)"
  report="$check_home/check.tsv"
  run_install "$check_home" --target=codex --category=communication --check --output "$report"
  [[ "$status" -eq 3 ]] || fail "--check reported missing managed files with exit $status: $output"
  grep -Fqx $'target\tkind\tpath\tstate' "$report" || fail "--check TSV header is missing"
  expected_row=$'codex\tskill-link\t'"$check_home"'/.agents/skills/communication-analysis'$'\tmissing'
  grep -Fq "$expected_row" "$report" ||
    fail "--check TSV did not report a missing Codex skill link"
  [[ ! -e "$check_home/.agents" && ! -e "$check_home/.codex" ]] ||
    fail "--check created files under HOME"
}

@test "--check resolves all targets before reporting drift" {
  all_home="$(mktemp -d)"
  all_report="$all_home/all-targets.tsv"
  run_install "$all_home" --target=all --category=communication --check --output "$all_report"
  [[ "$status" -eq 3 ]] || fail "--check --target=all missed missing target state"
  expected_all_row=$'codex\tskill-link\t'"$all_home"'/.agents/skills/communication-analysis'$'\tmissing'
  grep -Fq "$expected_all_row" "$all_report" ||
    fail "--check --target=all did not process its resolved Codex target"
}

@test "--check reports a clean managed inventory" {
  clean_home="$(mktemp -d)"
  HOME="$clean_home" "$INSTALL" --target=codex --category=communication >/dev/null
  run_install "$clean_home" --target=codex --category=communication --check
  [[ "$status" -eq 0 && "$output" == '--check: clean' ]] ||
    fail "--check did not report clean installed state: $output"
}

@test "--check compares rendered instruction marker blocks" {
  stale_home="$(mktemp -d)"
  HOME="$stale_home" "$INSTALL" --target=codex --category=communication --instructions >/dev/null
  instruction_file="$stale_home/.codex/AGENTS.md"
  begin_marker='<!-- >>> agents instructions (managed by install.sh, do not edit) >>> -->'
  end_marker='<!-- <<< agents instructions <<< -->'
  printf 'notes\n\n%s\nold rules\n%s\n' "$begin_marker" "$end_marker" >"$instruction_file"
  output_file="$stale_home/instructions.tsv"
  run_install "$stale_home" --target=codex --category=communication --instructions \
    --check --output "$output_file"
  [[ "$status" -eq 3 ]] || fail "stale instructions did not produce drift exit 3"
  expected_row=$'codex\tinstructions\t'"$instruction_file"$'\tstale'
  grep -Fq "$expected_row" "$output_file" || fail "--check missed stale instruction markers"
}

@test "--check detects moved-root paths in Codex agent TOMLs" {
  agent_home="$(mktemp -d)"
  HOME="$agent_home" "$INSTALL" --target=codex --category=architecture >/dev/null
  "$PYTHON" - "$agent_home/.codex/agents/coupling-analyst.toml" "$REPO_ROOT" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
path.write_text(path.read_text(encoding="utf-8").replace(sys.argv[2], "/old/checkout/agents"))
PY
  output_file="$agent_home/agents.tsv"
  run_install "$agent_home" --target=codex --category=architecture --check --output "$output_file"
  [[ "$status" -eq 3 ]] || fail "moved-root Codex agent TOML did not produce drift exit 3"
  expected_row=$'codex\tcodex-agent\t'"$agent_home/.codex/agents/coupling-analyst.toml"$'\tstale'
  grep -Fq "$expected_row" "$output_file" || fail "--check missed moved-root Codex agent TOML"
}

@test "--check detects moved-root Codex merge hooks" {
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
  run_install "$guard_home" --target=codex --category=communication --check --output "$output_file"
  [[ "$status" -eq 3 ]] || fail "moved-root merge guard did not produce drift exit 3"
  expected_row=$'codex\tmerge-guard\t'"$config_file"$'\tstale'
  grep -Fq "$expected_row" "$output_file" || fail "--check missed moved-root Codex merge guard"
  ! grep -Fq $'codex\tmerge-guard\t'"$config_file"$'\tuntrusted-hook' "$output_file" ||
    fail "the saved trust hash for the old-root hook was not recognized"
}

# A Codex config with both guards installed and a hooks.state table whose
# trust hashes match neither, so Codex would skip both hooks.
make_untrusted_guard_home() {
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
}

@test "--check reports merge and secret hooks Codex will skip until trusted" {
  make_untrusted_guard_home
  run_install "$untrusted_home" --target=codex --category=communication \
    --merge-guard --secret-guard --check --output "$output_file"
  [[ "$status" -eq 3 ]] || fail "untrusted Codex hook did not produce drift exit 3"
  [[ "$output" == *'untrusted-hook=2)'* ]] || fail "summary did not count both untrusted Codex hooks"
  expected_row=$'codex\tmerge-guard\t'"$config_file"$'\tuntrusted-hook'
  grep -Fqx "$expected_row" "$output_file" || fail "--check missed untrusted Codex merge hook"
  expected_row=$'codex\tsecret-guard\t'"$config_file"$'\tuntrusted-hook'
  grep -Fqx "$expected_row" "$output_file" || fail "--check missed untrusted Codex secret hook"
  [[ "$(grep -Fc $'\tuntrusted-hook' "$output_file")" -eq 2 ]] ||
    fail "--check did not report exactly two untrusted Codex hooks"
}

@test "--check handles partial Codex guard trust state" {
  make_untrusted_guard_home
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
  run_install "$untrusted_home" --target=codex --category=communication \
    --merge-guard --secret-guard --check --output "$output_file"
  [[ "$status" -eq 3 ]] ||
    fail "one untrusted Codex hook expected exit 3, got $status: $output"
  expected_row=$'codex\tmerge-guard\t'"$config_file"$'\tuntrusted-hook'
  grep -Fqx "$expected_row" "$output_file" || fail "--check missed the lone untrusted Codex hook"
  [[ "$(grep -Fc $'\tuntrusted-hook' "$output_file")" -eq 1 ]] ||
    fail "--check did not report exactly one untrusted Codex hook"
}

@test "--check identifies foreign files at managed paths" {
  foreign_home="$(mktemp -d)"
  mkdir -p "$foreign_home/.agents/skills/communication-analysis"
  output_file="$foreign_home/foreign.tsv"
  run_install "$foreign_home" --target=codex --category=communication --check --output "$output_file"
  [[ "$status" -eq 3 ]] || fail "foreign managed path did not produce drift exit 3"
  expected_row=$'codex\tskill-link\t'"$foreign_home/.agents/skills/communication-analysis"$'\tforeign'
  grep -Fq "$expected_row" "$output_file" || fail "--check missed a foreign Codex skill path"
}

@test "--check identifies duplicate managed blocks" {
  duplicate_home="$(mktemp -d)"
  HOME="$duplicate_home" "$INSTALL" --target=codex --category=architecture >/dev/null
  config_file="$duplicate_home/.codex/config.toml"
  begin_marker='# >>> agents routed-member skill overrides (managed by install.sh, do not edit) >>>'
  end_marker='# <<< agents routed-member skill overrides <<<'
  printf '\n%s\n[[skills.config]]\npath = "/duplicate/SKILL.md"\nenabled = false\n%s\n' \
    "$begin_marker" "$end_marker" >>"$config_file"
  output_file="$duplicate_home/duplicate.tsv"
  run_install "$duplicate_home" --target=codex --category=architecture --check --output "$output_file"
  [[ "$status" -eq 3 ]] || fail "duplicate managed blocks did not produce drift exit 3"
  expected_row=$'codex\trouted-member-overrides\t'"$config_file"$'\tduplicate'
  grep -Fq "$expected_row" "$output_file" || fail "--check missed duplicate managed blocks"
}

@test "--check reports the legacy MCP runtime venv without deleting it" {
  legacy_venv_home="$(mktemp -d)"
  HOME="$legacy_venv_home" "$INSTALL" --target=codex --category=communication >/dev/null
  mkdir -p "$legacy_venv_home/.codex/agents-mcp-runtime"
  output_file="$legacy_venv_home/legacy-venv.tsv"
  run_install "$legacy_venv_home" --target=codex --category=communication --check --output "$output_file"
  [[ "$status" -eq 3 ]] || fail "legacy MCP runtime venv did not produce drift exit 3: $output"
  expected_row=$'codex\tlegacy-mcp-runtime\t'"$legacy_venv_home/.codex/agents-mcp-runtime"$'\tstale'
  grep -Fq "$expected_row" "$output_file" || fail "--check missed the legacy MCP runtime venv"
  [[ -d "$legacy_venv_home/.codex/agents-mcp-runtime" ]] ||
    fail "--check deleted the legacy MCP runtime venv"
}

@test "--check rejects incompatible and incomplete options" {
  for check_args in \
    '--target=codex --check --dry-run' \
    '--target=codex --check --uninstall' \
    '--target=codex --output report.tsv' \
    '--target=bogus --check' \
    '--target=codex --check --output' \
    '--target=codex --check --output='; do
    # Intentional word splitting turns each fixed fixture into CLI arguments.
    # shellcheck disable=SC2086
    run_install "$(mktemp -d)" $check_args
    [[ "$status" -eq 2 ]] || fail "invalid --check arguments did not exit 2: $check_args"
  done
}
