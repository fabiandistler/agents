#!/usr/bin/env bats
# install-wizard.sh: scripted answers on stdin produce the matching install.sh
# command; without a terminal the wizard refuses instead of waiting.

bats_require_minimum_version 1.5.0

load install_helper

WIZARD="$REPO_ROOT/install-wizard.sh"

setup() {
  install_setup
  HOME="$(mktemp -d)"
  export HOME
}

# Runs the wizard from the repo root with the given answers, one per line, as
# if typed into a terminal. stdout is the printed command (or install output),
# stderr the prompts.
wizard() {
  local answers
  answers="$(printf '%s\n' "$@")"
  run --separate-stderr env INSTALL_WIZARD_ASSUME_TTY=1 bash -c \
    'cd "$1" && ./install-wizard.sh' _ "$REPO_ROOT" <<<"$answers"
}

@test "one target plus instructions prints that command" {
  # target, env, categories, instructions, merge guard, secret guard, dry run, install
  wizard codex "" "" y n n n n
  assert_success
  assert_line --index 0 './install.sh --target=codex --instructions'
  [[ ! -e "$HOME/.agents" ]] || fail "declining the install wrote $HOME/.agents"
}

@test "detected plus a category filter prints the detected target" {
  mkdir "$HOME/.codex"
  wizard detected "" architecture n n n n n
  assert_success
  assert_line --index 0 './install.sh --target=detected --category=architecture'
  [[ "$stderr" == *"detected (found: "*codex* ]] || fail "detected targets not shown: $stderr"
}

@test "categories accept numbers and names and keep their order" {
  mkdir "$HOME/.codex"
  # 1 is the first sorted category value (ai-ml).
  wizard opencode chat "1,workflow" n y y n n
  assert_success
  assert_line --index 0 \
    './install.sh --target=opencode --env=chat --category=ai-ml,workflow --merge-guard --secret-guard'
}

@test "claude skips the environment and category questions" {
  wizard claude y n n n n
  assert_success
  assert_line --index 0 './install.sh --target=claude --instructions'
  [[ "$stderr" != *"Categories:"* ]] || fail "asked for categories under claude"
}

@test "an invalid answer is asked again" {
  wizard bogus 2 "" "" maybe n n n n n
  assert_success
  assert_line --index 0 './install.sh --target=codex'
  [[ "$stderr" == *"not a choice: bogus"* ]] || fail "no re-prompt for the target"
  [[ "$stderr" == *"answer y or n"* ]] || fail "no re-prompt for yes/no"
}

@test "dry run chosen runs install.sh --dry-run and writes nothing" {
  wizard codex "" architecture n n n y n
  assert_success
  assert_line --index 0 './install.sh --target=codex --category=architecture'
  assert_line --partial '[dry-run] link '
  [[ "$stderr" == *"Nothing installed."* ]] || fail "missing the declined-install note"
  [[ ! -e "$HOME/.agents" ]] || fail "dry run wrote $HOME/.agents"
  [[ ! -e "$XDG_STATE_HOME/fabiandistler-agents" ]] || fail "dry run saved install state"
}

@test "confirming the install runs install.sh with the printed flags" {
  wizard codex "" architecture n n n n y
  assert_success
  assert_line --index 0 './install.sh --target=codex --category=architecture'
  [[ -L "$HOME/.agents/skills/architecture" ]] || fail "architecture router was not linked"
  [[ -f "$XDG_STATE_HOME/fabiandistler-agents/install.json" ]] || fail "install state not saved"
}

@test "without a terminal it exits 2 naming the flag-driven usage and does not wait" {
  # stdin stays open for 30 s; a wizard that read from it would block that long.
  local start=$SECONDS
  run --separate-stderr bash -c '"$1" < <(sleep 30)' _ "$WIZARD"
  assert_failure 2
  [[ "$stderr" == *"./install.sh --target="* ]] || fail "no pointer to the flags: $stderr"
  [[ "$stderr" == *"./install.sh --help"* ]] || fail "no pointer to --help: $stderr"
  ((SECONDS - start < 10)) || fail "the wizard waited for input"
}

@test "input that ends early exits 2 instead of waiting" {
  wizard codex
  assert_failure 2
  [[ "$stderr" == *"./install.sh --help"* ]] || fail "no pointer to --help: $stderr"
}

@test "the wizard never invokes node, npx or python3" {
  run grep -nwE 'node|npx|python3?' "$WIZARD"
  assert_failure
  # Stubs that record any call, first on PATH, for a run that declines both
  # the dry run and the install (only the wizard itself runs).
  local stubs calls="$BATS_TEST_TMPDIR/calls"
  stubs="$(mktemp -d)"
  for tool in node npx python3 python; do
    printf '#!/bin/sh\necho %s >>%q\n' "$tool" "$calls" >"$stubs/$tool"
    chmod +x "$stubs/$tool"
  done
  PATH="$stubs:$PATH" wizard all coding "" y y y n n
  assert_success
  assert_line --index 0 './install.sh --target=all --env=coding --instructions --merge-guard --secret-guard'
  [[ ! -e "$calls" ]] || fail "wizard called: $(cat "$calls")"
}

@test "--help exits 0 and an unknown argument exits 2" {
  run "$WIZARD" --help
  assert_success
  assert_line --index 0 --partial 'Usage: ./install-wizard.sh'
  run "$WIZARD" --bogus
  assert_failure 2
}
