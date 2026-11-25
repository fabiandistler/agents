# shellcheck shell=bash
# Shared by the check_all*.bats suites.

# make_bare_checkout: prints the path of a new checkout with nothing but
# check_all.sh and its sourced helper. Every check that needs a repo file
# fails there, and the Bats submodules are missing.
make_bare_checkout() {
  local checkout
  checkout="$(mktemp -d)"
  mkdir "$checkout/scripts"
  cp "$REPO_ROOT/scripts/check_all.sh" "$REPO_ROOT/scripts/require_python.sh" "$checkout/scripts/"
  printf '%s\n' "$checkout"
}
