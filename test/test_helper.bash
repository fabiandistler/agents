# shellcheck shell=bash
# Shared by every suite under test/: loads bats-support and bats-assert from
# the pinned submodules under test/bats/ and isolates each test's temp files.

load 'bats/bats-support/load'
load 'bats/bats-assert/load'

# shellcheck disable=SC2034 # used by the suites that load this file
REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
PYTHON="${PYTHON:-python3}"

common_setup() {
  set -o pipefail
  # mktemp -d lands in the per-test directory that Bats removes afterwards.
  export TMPDIR="$BATS_TEST_TMPDIR"
}
