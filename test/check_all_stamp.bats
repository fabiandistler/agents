#!/usr/bin/env bats
# scripts/check_all.sh: the pass stamp and --skip-passed (#954), which let the
# pre-push hooks skip checks that just passed on the pushed tree.

load test_helper
load check_all_helper

setup() {
  common_setup
  # A pre-push run of this suite exports the outer push's PRE_COMMIT_* values.
  unset "${!PRE_COMMIT@}"
}

# A git checkout whose instructions and docs checks are stubs: each exits
# $STUB_EXIT (default 0), appends to the tracked file with STUB_REWRITE=1 and
# commits with STUB_COMMIT=1. Every "runs the checks" test sets STUB_EXIT=1,
# so only a skipped run can exit 0.
make_stamp_checkout() {
  bare_checkout="$(make_bare_checkout)"
  local name
  for name in check_instructions check_docs; do
    cat >"$bare_checkout/scripts/$name.py" <<'PY'
import os
import subprocess
import sys

if os.environ.get("STUB_REWRITE"):
    with open("tracked.txt", "a") as tracked:
        tracked.write("rewritten\n")
if os.environ.get("STUB_COMMIT"):
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "moved"], check=True)
sys.exit(int(os.environ.get("STUB_EXIT", "0")))
PY
  done
  printf 'one\n' >"$bare_checkout/tracked.txt"
  git -C "$bare_checkout" init -q
  git -C "$bare_checkout" config user.name Test
  git -C "$bare_checkout" config user.email test@example.com
  commit_all init
  stamp="$bare_checkout/.git/check_all-pass"
  stamp_check_all="$bare_checkout/scripts/check_all.sh"
}

commit_all() {
  git -C "$bare_checkout" add -A
  git -C "$bare_checkout" commit -qm "$1"
}

head_tree() {
  git -C "$bare_checkout" rev-parse 'HEAD^{tree}'
}

# A passing run of both stub checks on the clean checkout writes the stamp.
stamp_both_checks() {
  "$stamp_check_all" --only docs,instructions >/dev/null
  [ -f "$stamp" ]
}

# run_skip_passed [ENV=VALUE...]: --skip-passed for both checks with a failing
# stub, as the pre-push hook of a push of HEAD.
run_skip_passed() {
  run env STUB_EXIT=1 PRE_COMMIT_TO_REF="$(git -C "$bare_checkout" rev-parse HEAD)" "$@" \
    "$stamp_check_all" --only docs,instructions --skip-passed
}

assert_checks_ran() {
  assert_failure 1
  assert_line 'FAIL docs (exit 1)'
  refute_output --partial 'skipped:'
}

@test "a passing run on a clean tree writes the stamp with HEAD's tree and its checks" {
  make_stamp_checkout
  run "$stamp_check_all" --only docs,instructions
  assert_success
  assert_equal "$(cat "$stamp")" "$(head_tree) docs,instructions"
  assert_equal "$(git -C "$bare_checkout" status --porcelain)" ""
}

@test "a failing run removes the stamp" {
  make_stamp_checkout
  stamp_both_checks
  run env STUB_EXIT=1 "$stamp_check_all" --only docs,instructions
  assert_failure 1
  [ ! -e "$stamp" ]
}

@test "an exit-3 run (a check MISSING) removes the stamp" {
  make_stamp_checkout
  stamp_both_checks
  run "$stamp_check_all" --only instructions,bats
  assert_failure 3
  assert_line --regexp '^PASS instructions \([0-9]+s\)$'
  [ ! -e "$stamp" ]
}

@test "a run started with a modified file leaves no stamp" {
  make_stamp_checkout
  stamp_both_checks
  printf 'two\n' >>"$bare_checkout/tracked.txt"
  run "$stamp_check_all" --only docs,instructions
  assert_success
  [ ! -e "$stamp" ]
}

@test "a run started with a staged file leaves no stamp" {
  make_stamp_checkout
  stamp_both_checks
  printf 'two\n' >>"$bare_checkout/tracked.txt"
  git -C "$bare_checkout" add tracked.txt
  run "$stamp_check_all" --only docs,instructions
  assert_success
  [ ! -e "$stamp" ]
}

@test "a run started with an untracked file leaves no stamp" {
  make_stamp_checkout
  stamp_both_checks
  printf 'new\n' >"$bare_checkout/new.txt"
  run "$stamp_check_all" --only docs,instructions
  assert_success
  [ ! -e "$stamp" ]
}

@test "a run whose check rewrites a file leaves no stamp" {
  make_stamp_checkout
  stamp_both_checks
  run env STUB_REWRITE=1 "$stamp_check_all" --only instructions
  assert_success
  [ ! -e "$stamp" ]
}

@test "a run during which HEAD moves leaves no stamp" {
  make_stamp_checkout
  stamp_both_checks
  run env STUB_COMMIT=1 "$stamp_check_all" --only instructions
  assert_success
  [ ! -e "$stamp" ]
}

@test "--skip-passed runs the checks after a commit that changes a file" {
  make_stamp_checkout
  stamp_both_checks
  printf 'two\n' >>"$bare_checkout/tracked.txt"
  commit_all change
  run_skip_passed
  assert_checks_ran
}

@test "--skip-passed runs the checks with an uncommitted edit" {
  make_stamp_checkout
  stamp_both_checks
  printf 'two\n' >>"$bare_checkout/tracked.txt"
  run_skip_passed
  assert_checks_ran
}

@test "--skip-passed runs the checks with a staged change" {
  make_stamp_checkout
  stamp_both_checks
  printf 'two\n' >>"$bare_checkout/tracked.txt"
  git -C "$bare_checkout" add tracked.txt
  run_skip_passed
  assert_checks_ran
}

@test "--skip-passed runs the checks with a new untracked file" {
  make_stamp_checkout
  stamp_both_checks
  printf 'new\n' >"$bare_checkout/new.txt"
  run_skip_passed
  assert_checks_ran
}

@test "--skip-passed runs the checks when the pushed commit's tree differs from HEAD's" {
  make_stamp_checkout
  older="$(git -C "$bare_checkout" rev-parse HEAD)"
  printf 'two\n' >>"$bare_checkout/tracked.txt"
  commit_all change
  stamp_both_checks
  run_skip_passed PRE_COMMIT_TO_REF="$older"
  assert_checks_ran
}

@test "--skip-passed runs the checks when the stamp lacks a selected check" {
  make_stamp_checkout
  "$stamp_check_all" --only docs >/dev/null
  assert_equal "$(cat "$stamp")" "$(head_tree) docs"
  run_skip_passed
  assert_checks_ran
}

@test "--skip-passed runs the checks on an empty stamp" {
  make_stamp_checkout
  : >"$stamp"
  run_skip_passed
  assert_checks_ran
}

@test "--skip-passed runs the checks on a malformed stamp" {
  make_stamp_checkout
  printf '%s\n' "$(head_tree)" >"$stamp"
  run_skip_passed
  assert_checks_ran
}

@test "--skip-passed runs the checks without a stamp" {
  make_stamp_checkout
  run_skip_passed
  assert_checks_ran
}

@test "--skip-passed runs the checks when the pushed commit is unknown" {
  make_stamp_checkout
  stamp_both_checks
  run env -u PRE_COMMIT_TO_REF STUB_EXIT=1 "$stamp_check_all" --only docs,instructions --skip-passed
  assert_checks_ran
}

@test "--skip-passed skips with one line when the pushed tree is the stamped one" {
  make_stamp_checkout
  stamp_both_checks
  run_skip_passed
  assert_success
  assert_output "skipped: tree $(head_tree) passed docs,instructions ($stamp)"
}

@test "--skip-passed skips after a message-only amend" {
  make_stamp_checkout
  stamp_both_checks
  git -C "$bare_checkout" commit -q --amend -m 'reworded'
  run_skip_passed
  assert_success
  assert_output "skipped: tree $(head_tree) passed docs,instructions ($stamp)"
}

@test "a prek pre-push hook hands check_all.sh the pushed commit, so --skip-passed skips" {
  command -v prek >/dev/null || skip "prek is not installed"
  make_stamp_checkout
  cat >"$bare_checkout/.pre-commit-config.yaml" <<'YAML'
repos:
  - repo: local
    hooks:
      - id: check-all-pre-push
        name: check_all.sh --skip-passed
        language: system
        entry: bash scripts/check_all.sh --only docs,instructions --skip-passed
        pass_filenames: false
        always_run: true
        verbose: true
        stages: [pre-push]
YAML
  commit_all 'add hook config'
  export PREK_HOME="$BATS_TEST_TMPDIR/prek-home"
  (cd "$bare_checkout" && prek install -t pre-push >/dev/null)
  git init -q --bare "$BATS_TEST_TMPDIR/remote.git"
  stamp_both_checks
  # A failing stub check: the push succeeds only if the hook skipped.
  run env STUB_EXIT=1 git -C "$bare_checkout" push "$BATS_TEST_TMPDIR/remote.git" HEAD:refs/heads/topic
  assert_success
  assert_output --partial "skipped: tree $(head_tree) passed docs,instructions ($stamp)"
}
