# shellcheck shell=bash
# Sourced, not run: the minimum interpreter for this repo's checks, kept in
# one place for check_all.sh and the install.sh Bats suites. The pytest suite
# and the Bats suites parse TOML with tomllib, which needs Python 3.11.

# require_python CALLER INTERPRETER: return 1 with one stderr line if
# INTERPRETER is missing or older than 3.11, so an old system python3 stops
# the run up front instead of failing, or passing, deep inside a check.
require_python() {
  "$2" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null && return 0
  echo "$1: PYTHON=$2 is missing or older than 3.11 (needs tomllib); set PYTHON=python3.11 or newer" >&2
  return 1
}
