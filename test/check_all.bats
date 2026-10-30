#!/usr/bin/env bats
# scripts/check_all.sh: the CLI contract (flags, exit codes, report lines) CI
# and the pre-push hooks rely on. The checks themselves are tested elsewhere.

load test_helper

setup() {
  common_setup
  CHECK_ALL="$REPO_ROOT/scripts/check_all.sh"
}

# A checkout with nothing but check_all.sh and its sourced helper: every check
# that needs a repo file fails there, and the Bats submodules are missing.
make_bare_checkout() {
  bare_checkout="$(mktemp -d)"
  mkdir "$bare_checkout/scripts"
  cp "$CHECK_ALL" "$REPO_ROOT/scripts/require_python.sh" "$bare_checkout/scripts/"
}

@test "--help prints the usage and exit codes" {
  run "$CHECK_ALL" --help
  assert_success
  assert_line --index 0 --partial 'Usage: scripts/check_all.sh'
  assert_output --partial '3 nothing failed but a check could not run'
}

@test "--list names every check with the tools it needs" {
  run "$CHECK_ALL" --list
  assert_success
  assert_line --regexp $'^manifest\t'
  assert_line --regexp $'^bats\tbash .* bats-submodules$'
  refute_output --partial 'install-smoke'
}

@test "an unknown argument exits 2 with the usage" {
  run "$CHECK_ALL" --bogus
  assert_failure 2
  assert_output --partial 'unknown argument: --bogus'
}

@test "an unknown check name exits 2 and lists the allowed ones" {
  run "$CHECK_ALL" --only nope
  assert_failure 2
  assert_output --partial 'unknown check: nope (allowed: manifest'
}

@test "--tail rejects a non-number" {
  run "$CHECK_ALL" --tail many
  assert_failure 2
  assert_output --partial '--tail needs a number, got: many'
}

@test "a missing interpreter stops the run with exit 4 before any check" {
  run env PYTHON="$BATS_TEST_TMPDIR/no-python" "$CHECK_ALL" --only instructions
  assert_failure 4
  assert_output --partial 'PYTHON='
  refute_output --partial 'PASS'
}

@test "a passing check prints PASS and a clean summary" {
  run "$CHECK_ALL" --only instructions
  assert_success
  assert_line --regexp '^PASS instructions \([0-9]+s\)$'
  assert_line 'summary: 0 failed, 0 missing'
}

@test "a failing check prints FAIL with its output, writes --output, and exits 1" {
  make_bare_checkout
  run "$bare_checkout/scripts/check_all.sh" --only instructions --output "$bare_checkout/full.log"
  assert_failure 1
  assert_line 'FAIL instructions (exit 2)'
  assert_line --partial '  | '
  assert_line 'summary: 1 failed (instructions), 0 missing'
  grep -q '^===== instructions (exit 2)$' "$bare_checkout/full.log"
}

@test "a missing Python tool names the pip of the interpreter the checks use" {
  "$PYTHON" -m venv --without-pip "$BATS_TEST_TMPDIR/bare"
  bare_python="$BATS_TEST_TMPDIR/bare/bin/python3"
  run env PYTHON="$bare_python" "$CHECK_ALL" --only pytest
  assert_failure 3
  assert_line "MISSING pytest: not installed: pytest pyyaml ($bare_python -m pip install -r scripts/check_all.requirements.txt)"
}

@test "missing Bats submodules report MISSING with the fix and exit 3" {
  make_bare_checkout
  run "$bare_checkout/scripts/check_all.sh" --only bats
  assert_failure 3
  assert_line 'MISSING bats: not installed: bats-submodules (git submodule update --init)'
  assert_line 'summary: 0 failed, 1 missing (bats)'
}
