#!/usr/bin/env bats
# scripts/maintenance-scan.sh: job selection, exit codes, and the findings it
# prints for a repository without R or Python tooling.

load test_helper

setup() {
  common_setup
  SCAN="$REPO_ROOT/scripts/maintenance-scan.sh"
  # The scanner reads the current directory as the repository to scan.
  scan_repo="$(mktemp -d)"
  cd "$scan_repo" || return
}

@test "no job exits 2 with the usage" {
  run "$SCAN"
  assert_failure 2
  assert_output --partial 'Usage: '
  assert_output --partial '<deps-audit|dead-exports|test-flakiness>'
}

@test "an unknown job exits 2 and points at the CI gate" {
  run "$SCAN" security-footguns
  assert_failure 2
  assert_line 'Unknown job: security-footguns'
  assert_output --partial 'run in the CI gate, not here'
}

@test "test-flakiness without a test directory says so and exits 0" {
  run "$SCAN" test-flakiness
  assert_success
  assert_output 'no tests/ or test/ directory found'
}

@test "test-flakiness lists time and randomness candidates with the seeds set" {
  mkdir tests
  printf 'test_that("x", {\n  now <- Sys.time()\n  set.seed(1)\n  sample(3)\n})\n' >tests/test-x.R
  run "$SCAN" test-flakiness
  assert_success
  assert_line '===== Candidates: time dependency ====='
  assert_line --partial 'tests/test-x.R:2:  now <- Sys.time()'
  assert_line --partial 'tests/test-x.R:4:  sample(3)'
  assert_line --partial 'tests/test-x.R:3:  set.seed(1)'
  # No sleep in the fixture: that section reports none.
  run grep -A1 'Candidates: sleep / timing' <<<"$output"
  assert_line --index 1 'none'
}

@test "test-flakiness skips vendored Bats libraries but scans the repo's own tests" {
  mkdir -p test/bats/bats-core/lib test/test_helper/bats-assert test/bats/bats-support
  printf 'curl https://example.invalid/vendored-core\n' >test/bats/bats-core/lib/net.bash
  printf 'curl https://example.invalid/vendored-assert\n' >test/test_helper/bats-assert/net.bash
  printf 'curl https://example.invalid/vendored-support\n' >test/bats/bats-support/net.bash
  printf 'curl https://example.invalid/own-test\n' >test/own.bats
  run "$SCAN" test-flakiness
  assert_success
  assert_line --partial 'test/own.bats:1:curl https://example.invalid/own-test'
  refute_output --partial 'vendored'
}

@test "dead-exports prints the evidence each removal needs" {
  run "$SCAN" dead-exports
  assert_success
  assert_line '===== Required evidence per removal ====='
  assert_output --partial 'git log -S<name>'
}

@test "deps-audit recommends Dependabot or Renovate when neither is configured" {
  run "$SCAN" deps-audit
  assert_success
  assert_line 'Neither Renovate nor Dependabot is configured. Add a recommendation to the report:'
}

@test "deps-audit defers update work to a configured Dependabot" {
  mkdir .github
  : >.github/dependabot.yml
  run "$SCAN" deps-audit
  assert_success
  assert_line 'Renovate/Dependabot is configured - the update work belongs there.'
}
