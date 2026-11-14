#!/usr/bin/env bats
# .claude/hooks/lint-on-edit.sh: the PostToolUse hook that runs the pinned
# ruff hooks through prek on an edited Python file (#806). A stub prek first
# on PATH records its calls and keeps the tests offline.

bats_require_minimum_version 1.5.0
load test_helper

setup() {
  common_setup
  HOOK="$REPO_ROOT/.claude/hooks/lint-on-edit.sh"
  project="$BATS_TEST_TMPDIR/project"
  mkdir -p "$project/scripts"
  project="$(cd "$project" && pwd -P)"
  export CLAUDE_PROJECT_DIR="$project"
  prek_calls="$BATS_TEST_TMPDIR/prek-calls"
  stub_prek
}

# stub_prek: a prek first on PATH that appends its arguments to $prek_calls,
# prints "prek run <n>" and exits with $STUB_PREK_EXIT_<n> (default 0).
stub_prek() {
  local stub_bin="$BATS_TEST_TMPDIR/stub-bin"
  mkdir -p "$stub_bin"
  cat >"$stub_bin/prek" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >>$(printf '%q' "$prek_calls")
n=\$(wc -l <$(printf '%q' "$prek_calls"))
echo "prek run \$n"
code_var="STUB_PREK_EXIT_\$n"
exit "\${!code_var:-0}"
EOF
  chmod +x "$stub_bin/prek"
  stub_path="$stub_bin:$(path_without prek)"
}

# hook_input PATH: the PostToolUse stdin JSON of an Edit of PATH.
hook_input() {
  "$PYTHON" -c 'import json, sys; print(json.dumps({"tool_name": "Edit", "tool_input": {"file_path": sys.argv[1]}}))' "$1"
}

# run_hook PATH: runs the hook with the stub prek first on PATH.
run_hook() {
  run --separate-stderr env PATH="$stub_path" "$HOOK" < <(hook_input "$1")
}

refute_prek_called() {
  [ ! -e "$prek_calls" ]
}

@test "the hook is tracked, executable and names its Bats exemption" {
  run git -C "$REPO_ROOT" ls-files --error-unmatch .claude/hooks/lint-on-edit.sh
  assert_success
  [ -x "$HOOK" ]
  run grep -F 'Bats exemption: a hook (instructions/45-shell-scripts.md).' "$HOOK"
  assert_success
}

@test "a Markdown file is skipped without calling prek" {
  touch "$project/README.md"
  run_hook "$project/README.md"
  assert_success
  assert_output ''
  [ -z "$stderr" ]
  refute_prek_called
}

@test "a Python file outside the project is skipped without calling prek" {
  outside="$BATS_TEST_TMPDIR/elsewhere/tool.py"
  mkdir -p "${outside%/*}"
  touch "$outside"
  run_hook "$outside"
  assert_success
  assert_output ''
  [ -z "$stderr" ]
  refute_prek_called
}

@test "a deleted Python file is skipped without calling prek" {
  run_hook "$project/scripts/gone.py"
  assert_success
  assert_output ''
  [ -z "$stderr" ]
  refute_prek_called
}

@test "a Python file runs the ruff hooks twice on that file" {
  touch "$project/scripts/tool.py"
  run_hook "$project/scripts/tool.py"
  assert_success
  assert_output ''
  [ -z "$stderr" ]
  run cat "$prek_calls"
  assert_output "run ruff-check ruff-format --files $project/scripts/tool.py
run ruff-check ruff-format --files $project/scripts/tool.py"
}

@test "a failing second run exits 2 with its output on stderr" {
  touch "$project/scripts/tool.py"
  STUB_PREK_EXIT_2=1 run_hook "$project/scripts/tool.py"
  assert_failure 2
  assert_output ''
  [ "$stderr" = "prek run 2" ]
}

@test "a passing second run after a failing first one exits 0 silently" {
  touch "$project/scripts/tool.py"
  STUB_PREK_EXIT_1=1 run_hook "$project/scripts/tool.py"
  assert_success
  assert_output ''
  [ -z "$stderr" ]
}

@test "without prek the hook exits 2 with one line naming prek and its install" {
  touch "$project/scripts/tool.py"
  run --separate-stderr env PATH="$(path_without prek)" "$HOOK" < <(hook_input "$project/scripts/tool.py")
  assert_failure 2
  assert_output ''
  [ "${#stderr_lines[@]}" -eq 1 ]
  [[ "$stderr" == *"MISSING prek"*"pip install -r scripts/check_all.requirements.txt"* ]]
}
