#!/usr/bin/env bats
# scripts/maintenance-scan.sh: job selection, exit codes, and the findings it
# prints for a repository without R or Python tooling. The scanner is vendored
# from fabiandistler/repo-maintenance (scripts/vendor_repo_maintenance.py), so
# a failure here after a re-vendor means upstream changed its behaviour.

load test_helper

setup() {
  common_setup
  SCAN="$REPO_ROOT/scripts/maintenance-scan.sh"
  # The scanner scans the Git repository around the current directory.
  scan_repo="$(mktemp -d)"
  cd "$scan_repo" || return
  git init -q
}

@test "--help prints the usage with the exit codes and exits 0" {
  run "$SCAN" --help
  assert_success
  assert_line --index 0 'Usage: scripts/maintenance-scan.sh <deps-audit|dead-exports|test-flakiness>'
  assert_line 'Exit codes:'
}

@test "no job exits 2 and points at --help" {
  run "$SCAN"
  assert_failure 2
  assert_output 'No job given. Run with --help.'
}

@test "an unknown job exits 2 and points at the CI gate" {
  run "$SCAN" security-footguns
  assert_failure 2
  assert_line 'Unknown job: security-footguns (see --help)'
  assert_line 'security-footguns and dead-code (local) run in the CI gate, not here.'
}

@test "outside a Git repository the scan exits 3" {
  mkdir "$BATS_TEST_TMPDIR/plain"
  cd "$BATS_TEST_TMPDIR/plain" || return
  # Stop the repository search at the test directory, wherever TMPDIR lives.
  GIT_CEILING_DIRECTORIES="$BATS_TEST_TMPDIR" run "$SCAN" deps-audit
  assert_failure 3
  assert_output 'Not a Git repository.'
}

@test "test-flakiness without a test directory notes the skip and exits 0" {
  run "$SCAN" test-flakiness
  assert_success
  assert_output '[skipped] no tests/ or test/ directory -> flakiness scan'
}

# The fixtures below split every scanner trigger into concatenated quotes, so
# a test-flakiness scan of this repository does not report this file.

@test "test-flakiness lists time and randomness candidates with the seeds set" {
  local now_call='Sys.''time()' seed_call='set.''seed(1)' draw_call='sam''ple(3)'
  mkdir tests
  printf 'test_that("x", {\n  now <- %s\n  %s\n  %s\n})\n' \
    "$now_call" "$seed_call" "$draw_call" >tests/test-x.R
  run "$SCAN" test-flakiness
  assert_success
  assert_line '===== Candidates: time dependency ====='
  assert_line --partial "tests/test-x.R:2:  now <- $now_call"
  assert_line --partial "tests/test-x.R:4:  $draw_call"
  assert_line --partial "tests/test-x.R:3:  $seed_call"
  # No sleep in the fixture: that section reports none.
  run grep -A1 'Candidates: sleep / timing' <<<"$output"
  assert_line --index 1 'none'
}

@test "test-flakiness run from a subdirectory scans from the repository root" {
  local now_call='Sys.''time()'
  mkdir -p tests docs
  printf 'now <- %s\n' "$now_call" >tests/test-x.R
  cd docs || return
  run "$SCAN" test-flakiness
  assert_success
  assert_line --partial "tests/test-x.R:1:now <- $now_call"
}

@test "test-flakiness skips vendored Bats libraries but scans the repo's own tests" {
  local fetch='cu''rl http''s://example.invalid'
  mkdir -p test/bats/bats-core/lib test/test_helper/bats-assert test/bats/bats-support
  printf '%s/vendored-core\n' "$fetch" >test/bats/bats-core/lib/net.bash
  printf '%s/vendored-assert\n' "$fetch" >test/test_helper/bats-assert/net.bash
  printf '%s/vendored-support\n' "$fetch" >test/bats/bats-support/net.bash
  printf '%s/own-test\n' "$fetch" >test/own.bats
  run "$SCAN" test-flakiness
  assert_success
  assert_line --partial "test/own.bats:1:$fetch/own-test"
  refute_output --partial 'vendored'
}

@test "dead-exports without an R or Python package exits 3" {
  run "$SCAN" dead-exports
  assert_failure 3
  assert_output 'No DESCRIPTION, pyproject.toml or requirements.txt found. Nothing to scan.'
}

@test "deps-audit skips the package audit and recommends Dependabot or Renovate" {
  run "$SCAN" deps-audit
  assert_success
  assert_line '[skipped] no DESCRIPTION, pyproject.toml or requirements.txt -> R and Python package audit'
  assert_line 'Neither Renovate nor Dependabot is configured. Add a recommendation to the report:'
}

@test "deps-audit defers update work to a configured Dependabot" {
  mkdir .github
  : >.github/dependabot.yml
  run "$SCAN" deps-audit
  assert_success
  assert_line 'Renovate/Dependabot is configured - the update work belongs there.'
}
