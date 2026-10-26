#!/usr/bin/env bats
# install.sh's saved install state: --update replays it, --uninstall keeps it
# in step, and --target=detected resolves targets before saving them.

load install_helper

setup() {
  install_setup
}

# run_install_state HOME STATE ARGS...: install.sh with its own HOME and
# XDG_STATE_HOME through Bats' run.
run_install_state() {
  local home="$1" state_home="$2"
  shift 2
  run env HOME="$home" XDG_STATE_HOME="$state_home" "$INSTALL" "$@"
}

# saved_state_is JSON: the keys in JSON have these values in $state_file.
saved_state_is() {
  "$PYTHON" - "$state_file" "$1" <<'PY'
import json
import sys

state = json.load(open(sys.argv[1], encoding="utf-8"))
expected = json.loads(sys.argv[2])
assert {key: state[key] for key in expected} == expected, state
PY
}

# A codex install with every option set, so its saved state has all keys.
install_with_saved_state() {
  update_home="$(mktemp -d)"
  state_home="$update_home/xdg-state"
  state_file="$state_home/fabiandistler-agents/install.json"
  HOME="$update_home" XDG_STATE_HOME="$state_home" "$INSTALL" \
    --target=codex --env=coding --category=architecture --instructions \
    --merge-guard --secret-guard >/dev/null
}

# A PATH with just the commands install.sh needs to print its usage: no agent
# CLI is found there.
make_bare_bin() {
  bare_bin="$(mktemp -d)"
  ln -s "$(command -v bash)" "$bare_bin/bash"
  ln -s "$(command -v dirname)" "$bare_bin/dirname"
  ln -s "$(command -v sed)" "$bare_bin/sed"
  ln -s "$(command -v cat)" "$bare_bin/cat"
}

@test "full uninstall deletes the saved state, so --update has nothing to replay" {
  home="$(mktemp -d)"
  state_home="$home/xdg-state"
  state_file="$state_home/fabiandistler-agents/install.json"
  run_install_state "$home" "$state_home" --target=codex --category=communication
  [[ "$status" -eq 0 && -f "$state_file" ]] || fail "install for uninstall test failed: $output"
  before="$(cat "$state_file")"
  run_install_state "$home" "$state_home" --target=codex --category=communication --uninstall --dry-run
  [[ "$status" -eq 0 ]] || fail "uninstall --dry-run failed: $output"
  [[ "$output" == *"would delete install state $state_file"* ]] ||
    fail "uninstall --dry-run did not announce the state deletion"
  [[ "$(cat "$state_file")" == "$before" ]] || fail "uninstall --dry-run changed the saved state"
  run_install_state "$home" "$state_home" --target=codex --category=communication --uninstall
  [[ "$status" -eq 0 ]] || fail "uninstall failed: $output"
  [[ ! -e "$state_file" ]] || fail "uninstall of the full saved selection kept install.json"
  run_install_state "$home" "$state_home" --update --dry-run
  [[ "$status" -eq 4 ]] || fail "--update after a full uninstall exited $status instead of 4"
  [[ ! -e "$home/.agents/skills/documentation" ]] || fail "--update reinstalled an uninstalled skill"
}

@test "partial uninstall keeps the rest in the saved state; one it cannot express leaves it unchanged" {
  home="$(mktemp -d)"
  state_home="$home/xdg-state"
  state_file="$state_home/fabiandistler-agents/install.json"
  run_install_state "$home" "$state_home" --target=all --category=communication,workflow --instructions
  [[ "$status" -eq 0 ]] || fail "install for partial uninstall test failed: $output"
  run_install_state "$home" "$state_home" --target=codex --category=communication,workflow --uninstall
  [[ "$status" -eq 0 ]] || fail "target uninstall failed: $output"
  saved_state_is '{"targets": ["claude", "opencode"], "category": "communication,workflow", "instructions": true}' ||
    fail "target uninstall did not drop just that target from the saved state"
  run_install_state "$home" "$state_home" --target=all --category=workflow --uninstall --dry-run
  [[ "$output" == *"would rewrite install state $state_file"* ]] ||
    fail "uninstall --dry-run did not announce the state rewrite"
  run_install_state "$home" "$state_home" --target=all --category=workflow --uninstall
  [[ "$status" -eq 0 ]] || fail "category uninstall failed: $output"
  saved_state_is '{"targets": ["claude", "opencode"], "category": "communication", "instructions": true}' ||
    fail "category uninstall did not drop just that category from the saved state"
  run_install_state "$home" "$state_home" --update
  [[ "$status" -eq 0 ]] || fail "--update after a partial uninstall failed: $output"
  [[ ! -e "$home/.agents/skills/documentation" ]] || fail "--update reinstalled the uninstalled codex target"
  [[ -L "$home/.config/opencode/skills/documentation" ]] || fail "--update dropped the remaining opencode skills"
  [[ ! -e "$home/.config/opencode/skills/natural-planning" ]] ||
    fail "--update reinstalled the uninstalled category"

  before="$(cat "$state_file")"
  run_install_state "$home" "$state_home" --target=opencode --category=communication --env=chat --uninstall
  [[ "$status" -eq 0 ]] || fail "unrepresentable uninstall failed: $output"
  [[ "$output" == *"install state keeps"* ]] ||
    fail "uninstall that the state cannot express did not say so"
  [[ "$(cat "$state_file")" == "$before" ]] || fail "unrepresentable uninstall changed the saved state"
}

@test "successful install saves resolved options and repo root" {
  install_with_saved_state
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
}

@test "install state uses ~/.local/state when XDG_STATE_HOME is unset" {
  default_state_home="$(mktemp -d)"
  HOME="$default_state_home" XDG_STATE_HOME="" "$INSTALL" \
    --target=codex --category=communication >/dev/null
  [[ -f "$default_state_home/.local/state/fabiandistler-agents/install.json" ]] ||
    fail "state without XDG_STATE_HOME did not use ~/.local/state"
}

@test "dry-run does not save install state" {
  no_state_home="$(mktemp -d)"
  no_state_dir="$no_state_home/xdg-state"
  run_install_state "$no_state_home" "$no_state_dir" --target=codex --category=communication --dry-run
  [[ "$status" -eq 0 ]] || fail "initial dry-run failed: $output"
  [[ ! -e "$no_state_dir/fabiandistler-agents/install.json" ]] ||
    fail "dry-run saved install state"
}

@test "--update replays filters, guards, and on-demand instruction outputs" {
  install_with_saved_state

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
  run_install_state "$update_home" "$state_home" --update
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
}

@test "--update --dry-run previews without writing files or state" {
  install_with_saved_state

  rm "$update_home/.agents/skills/architecture"
  rm "$update_home/.agents/instructions/80-agent-pipelines.md"
  state_copy="$update_home/state-before-dry-run.json"
  cp "$state_file" "$state_copy"
  run_install_state "$update_home" "$state_home" --update --dry-run
  [[ "$status" -eq 0 ]] || fail "--update --dry-run failed: $output"
  [[ ! -e "$update_home/.agents/skills/architecture" &&
    ! -e "$update_home/.agents/instructions/80-agent-pipelines.md" ]] ||
    fail "--update --dry-run changed managed files"
  diff -q "$state_file" "$state_copy" >/dev/null || fail "--update --dry-run changed saved state"
}

@test "--update reports missing state with its own exit code and bootstrap option" {
  missing_home="$(mktemp -d)"
  missing_state_home="$missing_home/empty-state"
  run_install_state "$missing_home" "$missing_state_home" --update
  [[ "$status" -eq 4 ]] || fail "missing update state exited $status instead of 4"
  [[ "$output" == *'--target='* ]] || fail "missing-state error did not name --target"
}

@test "--update rebases marker-owned files and links after a checkout move" {
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
  run_install_state "$move_home" "$move_state" --update
  [[ "$status" -eq 0 ]] || fail "--update failed after a checkout move: $output"
  [[ "$(readlink "$moved_skill_link")" == "$REPO_ROOT/skills/architecture" ]] ||
    fail "--update did not retarget the Codex skill link from the previous checkout"
  [[ "$(readlink "$moved_plugin_link")" == "$REPO_ROOT/scripts/opencode/pr-merge-guard.js" ]] ||
    fail "--update did not retarget the OpenCode guard link from the previous checkout"
  "$PYTHON" - "$move_home" "$move_file" "$REPO_ROOT" "$old_root" <<'PY' || fail "--update did not rebase marker-owned paths and preserve external content"
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
}

@test "--update preserves foreign files and links at managed paths" {
  foreign_home="$(mktemp -d)"
  foreign_state="$foreign_home/xdg-state"
  HOME="$foreign_home" XDG_STATE_HOME="$foreign_state" "$INSTALL" \
    --target=codex --category=architecture >/dev/null
  foreign_agent="$foreign_home/.codex/agents/coupling-analyst.toml"
  printf 'human-owned agent\n' >"$foreign_agent"
  foreign_link="$foreign_home/.agents/skills/architecture"
  rm "$foreign_link"
  ln -s "$foreign_home/outside-skill" "$foreign_link"
  run_install_state "$foreign_home" "$foreign_state" --update
  [[ "$status" -eq 0 ]] || fail "--update failed while preserving foreign paths: $output"
  [[ "$(cat "$foreign_agent")" == 'human-owned agent' ]] ||
    fail "--update overwrote a Codex agent without its marker"
  [[ "$(readlink "$foreign_link")" == "$foreign_home/outside-skill" ]] ||
    fail "--update replaced a foreign skill link"
}

@test "plain install from a moved checkout rebases the previous checkout's links" {
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
}

@test "--target=detected combines installed commands and config directories" {
  detected_home="$(mktemp -d)"
  detected_state="$detected_home/xdg-state"
  detected_bin="$detected_home/bin"
  mkdir -p "$detected_bin" "$detected_home/.codex" "$detected_home/.config/opencode"
  printf '#!/bin/sh\nexit 0\n' >"$detected_bin/claude"
  chmod +x "$detected_bin/claude"
  [[ ! -d "$detected_home/.claude" ]] || fail "CLI detection fixture already has Claude config"
  run env HOME="$detected_home" XDG_STATE_HOME="$detected_state" \
    PATH="$detected_bin:$PATH" "$INSTALL" --target=detected --category=communication
  [[ "$status" -eq 0 ]] || fail "--target=detected failed: $output"
  [[ "$output" == *'detected targets: claude, codex, opencode'* ]] ||
    fail "--target=detected did not print its resolved targets: $output"
  state_file="$detected_state/fabiandistler-agents/install.json"
  "$PYTHON" - "$state_file" <<'PY' || fail "detected install did not save resolved targets"
import json
import sys

targets = json.load(open(sys.argv[1], encoding="utf-8"))["targets"]
assert targets == ["claude", "codex", "opencode"]
assert "detected" not in targets
PY
  cp "$state_file" "$detected_home/state-before-check.json"
  run env HOME="$detected_home" XDG_STATE_HOME="$detected_state" \
    PATH="$detected_bin:$PATH" "$INSTALL" --target=detected --category=communication --check
  [[ "$status" -eq 0 && "$output" == *'--check: clean'* ]] ||
    fail "--check did not resolve detected targets read-only: $output"
  diff -q "$state_file" "$detected_home/state-before-check.json" >/dev/null ||
    fail "--check with detected targets changed saved install state"
}

@test "bare invocation exits 2 without writing and lists detected" {
  bare_home="$(mktemp -d)"
  bare_state="$bare_home/xdg-state"
  make_bare_bin
  run env HOME="$bare_home" XDG_STATE_HOME="$bare_state" PATH="$bare_bin" \
    "$INSTALL"
  [[ "$status" -eq 2 && "$output" == *'missing --target=claude|codex|opencode|all|detected'* ]] ||
    fail "bare installer invocation did not explain the target options: $output"
  [[ ! -e "$bare_home/.agents" && ! -e "$bare_home/.codex" &&
    ! -e "$bare_home/.claude" && ! -e "$bare_home/.config" &&
    ! -e "$bare_state/fabiandistler-agents/install.json" ]] ||
    fail "bare installer invocation wrote into HOME or XDG state"
}

@test "--target=detected with no installations exits 2 without writing" {
  make_bare_bin
  no_agent_home="$(mktemp -d)"
  no_agent_state="$no_agent_home/xdg-state"
  run env HOME="$no_agent_home" XDG_STATE_HOME="$no_agent_state" PATH="$bare_bin" \
    "$INSTALL" --target=detected
  [[ "$status" -eq 2 && "$output" == *'no agent commands or config directories detected'* ]] ||
    fail "empty detected target set did not exit 2 clearly: $output"
  [[ ! -e "$no_agent_home/.agents" && ! -e "$no_agent_home/.codex" &&
    ! -e "$no_agent_home/.claude" && ! -e "$no_agent_home/.config" &&
    ! -e "$no_agent_state/fabiandistler-agents/install.json" ]] ||
    fail "empty detected target set wrote into HOME or XDG state"
}
