#!/usr/bin/env bats
# scripts/factory-repo-setup.sh: every stage in dry-run and apply mode against
# a stubbed gh. The stub logs each call's argv to $GH_LOG and answers from the
# GH_* variables a test sets; a write is a logged `api -X ...` or `secret set`.

bats_require_minimum_version 1.5.0

load test_helper

REPO=acme/widgets
TOKEN_VALUE=sk-ant-oat01-do-not-print-me

setup() {
  common_setup
  # A copy of the wizard beside the real label policy and a fake onboarding
  # check, so the Verify stage makes no network call.
  scripts="$BATS_TEST_TMPDIR/scripts"
  mkdir -p "$scripts" "$BATS_TEST_TMPDIR/bin"
  cp "$REPO_ROOT/scripts/factory-repo-setup.sh" "$REPO_ROOT/scripts/factory_repo_setup.py" \
    "$REPO_ROOT/scripts/issue_triage_policy.py" "$scripts/"
  cat >"$scripts/factory_onboarding_check.py" <<'PY'
import os, sys
print(f"check argv={' '.join(sys.argv[1:])} token={os.environ.get('GH_TOKEN', '')}")
print("CANNOT-VERIFY\tapp-installation\tcheck by hand")
sys.exit(int(os.environ.get("FAKE_CHECK_EXIT", "0")))
PY
  WIZARD="$scripts/factory-repo-setup.sh"

  export GH_LOG="$BATS_TEST_TMPDIR/gh.log" GH_SECRET_STDIN="$BATS_TEST_TMPDIR/secret.stdin"
  export GH_PUT_BODY="$BATS_TEST_TMPDIR/put.json" BROWSER_LOG="$BATS_TEST_TMPDIR/browser.log"
  : >"$GH_LOG"
  cat >"$BATS_TEST_TMPDIR/bin/gh" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$GH_LOG"
r=acme/widgets
case "$*" in
  "auth status") exit "${GH_AUTH_STATUS:-0}" ;;
  "auth token") echo session-token ;;
  "api repos/$r --jq .visibility")
    [[ -n "${GH_VISIBILITY:-}" ]] || { echo "HTTP 404: Not Found" >&2; exit 1; }
    echo "$GH_VISIBILITY" ;;
  "api --paginate repos/$r/labels?per_page=100 --jq .[].name") printf '%s' "${GH_LABELS:-}" ;;
  "api -X POST repos/$r/labels -f name="*) echo '{}' ;;
  "api --paginate repos/$r/actions/secrets?per_page=100 --jq .secrets[].name") printf '%s' "${GH_SECRETS:-}" ;;
  "secret set CLAUDE_CODE_OAUTH_TOKEN --repo $r")
    cat >"$GH_SECRET_STDIN"
    exit "${GH_SECRET_SET_STATUS:-0}" ;;
  "api repos/$r/actions/permissions --jq .allowed_actions") echo "${GH_ALLOWED_ACTIONS:-all}" ;;
  "api repos/$r/actions/permissions/selected-actions") echo "$GH_SELECTED" ;;
  "api -X PUT repos/$r/actions/permissions/selected-actions --input -") cat >"$GH_PUT_BODY" ;;
  *) echo "unexpected gh call: $*" >&2; exit 99 ;;
esac
SH
  # open_url tries wslview first: the stub records the URL instead of a browser.
  printf '#!/usr/bin/env bash\nprintf "%%s\\n" "$1" >>"$BROWSER_LOG"\n' >"$BATS_TEST_TMPDIR/bin/wslview"
  chmod +x "$BATS_TEST_TMPDIR/bin/gh" "$BATS_TEST_TMPDIR/bin/wslview"
  PATH="$BATS_TEST_TMPDIR/bin:$PATH"

  # A repo in which nothing is set up yet.
  export GH_VISIBILITY=private GH_LABELS="" GH_SECRETS="" GH_ALLOWED_ACTIONS=all
}

# The labels the wizard must create: the state labels and the categories.
ALL_LABELS=$'needs-triage\nneeds-info\nready-for-agent\nready-for-human\nwontfix\nbug\nenhancement'
FULL_SELECTED='{"github_owned_allowed":true,"verified_allowed":false,"patterns_allowed":["fabiandistler/agents/.github/workflows/*","actions/checkout@*","actions/setup-python@*","actions/upload-artifact@*","actions/download-artifact@*","anthropics/claude-code-action@*"]}'

# The gh calls that change something.
writes() { grep -E '^(api -X |secret set)' "$GH_LOG" || true; }

# apply ANSWER...: runs --apply with the answers on stdin, one per line.
apply() {
  local answers
  answers="$(printf '%s\n' "$@")"
  run --separate-stderr "$WIZARD" --repo "$REPO" --apply "${extra_args[@]}" <<<"$answers"
}
extra_args=()

assert_no_token_anywhere() {
  [[ "$output$stderr" != *"$TOKEN_VALUE"* ]] || fail "the token appeared in the output"
  ! grep -qF "$TOKEN_VALUE" "$GH_LOG" || fail "the token appeared in a gh argv"
}

# ── usage ────────────────────────────────────────────────────────────────

@test "--help prints the usage with the exit codes and exits 0" {
  run "$WIZARD" --help
  assert_success
  assert_line --index 0 --partial 'Usage: scripts/factory-repo-setup.sh --repo OWNER/NAME'
  assert_line --partial 'Exit: 0 done'
  [[ ! -s "$GH_LOG" ]] || fail "--help called gh"
}

@test "no --repo exits 2 and names the flag" {
  run --separate-stderr "$WIZARD"
  assert_failure 2
  [[ "$stderr" == *"--repo OWNER/NAME is required"* ]] || fail "stderr: $stderr"
}

@test "--dry-run with --apply exits 2" {
  run --separate-stderr "$WIZARD" --repo "$REPO" --dry-run --apply
  assert_failure 2
  [[ "$stderr" == *"exclude each other"* ]] || fail "stderr: $stderr"
}

@test "an unreadable --token-file exits 2 before any gh call" {
  run --separate-stderr "$WIZARD" --repo "$REPO" --token-file "$BATS_TEST_TMPDIR/absent"
  assert_failure 2
  [[ ! -s "$GH_LOG" ]] || fail "gh was called: $(cat "$GH_LOG")"
}

# ── stage 1: preconditions ───────────────────────────────────────────────

@test "a missing repo exits 3 before any write, in apply mode" {
  unset GH_VISIBILITY
  apply "" y y
  assert_failure 3
  [[ "$stderr" == *"$REPO does not exist or this gh login cannot reach it"* ]] || fail "stderr: $stderr"
  assert_equal "$(writes)" ""
  [[ ! -e "$BROWSER_LOG" ]] || fail "opened a browser"
}

@test "a missing repo exits 3 in dry-run mode too" {
  unset GH_VISIBILITY
  run --separate-stderr "$WIZARD" --repo "$REPO"
  assert_failure 3
  assert_equal "$(writes)" ""
}

@test "gh not logged in exits 3 before any write" {
  export GH_AUTH_STATUS=1
  apply "" y y
  assert_failure 3
  [[ "$stderr" == *"gh auth login"* ]] || fail "stderr: $stderr"
  assert_equal "$(writes)" ""
}

@test "a private repo is told it gets no ruleset; a public one is pointed at it" {
  run "$WIZARD" --repo "$REPO"
  assert_success
  assert_line --partial 'Visibility: private.'
  assert_line --partial 'no ruleset, so no check can be required'
  GH_VISIBILITY=public run "$WIZARD" --repo "$REPO"
  assert_success
  assert_line --partial 'Public: add a ruleset that requires the checks'
}

# ── dry run as a whole ───────────────────────────────────────────────────

@test "dry run is the default, prints every planned write and performs none" {
  export GH_ALLOWED_ACTIONS=selected GH_SELECTED='{"github_owned_allowed":true,"verified_allowed":false,"patterns_allowed":[]}'
  run --separate-stderr "$WIZARD" --repo "$REPO"
  assert_success
  local label
  while IFS= read -r label; do
    assert_line --partial "[dry-run] would create label $label"
  done <<<"$ALL_LABELS"
  assert_line --partial '[dry-run] would set secret CLAUDE_CODE_OAUTH_TOKEN from hidden entry'
  assert_line --partial '[dry-run] would allow fabiandistler/agents/.github/workflows/*'
  assert_line --partial '[dry-run] would allow anthropics/claude-code-action@*'
  assert_line --partial "[dry-run] --apply opens https://github.com/$REPO/settings/installations"
  assert_line --partial 'Dry run: nothing changed.'
  assert_equal "$(writes)" ""
  [[ ! -e "$BROWSER_LOG" ]] || fail "dry run opened a browser"
}

# ── stage 2: labels ──────────────────────────────────────────────────────

@test "apply creates only the missing labels and leaves an existing one alone" {
  export GH_LABELS=$'Bug\nneeds-triage\nsomething-else'
  extra_args=(--token-file "$BATS_TEST_TMPDIR/token")
  printf '%s\n' "$TOKEN_VALUE" >"$BATS_TEST_TMPDIR/token"
  apply "" y y
  assert_success
  assert_line --partial 'exists, left as it is: needs-triage'
  assert_line --partial 'exists, left as it is: bug'
  run writes
  assert_line 'api -X POST repos/acme/widgets/labels -f name=needs-info'
  assert_line 'api -X POST repos/acme/widgets/labels -f name=enhancement'
  refute_line --partial 'name=needs-triage'
  refute_line --partial 'name=bug'
}

@test "dry run lists an existing label as left alone and plans no write for it" {
  export GH_LABELS="$ALL_LABELS"
  run "$WIZARD" --repo "$REPO"
  assert_success
  assert_line --partial 'All labels exist; nothing to create.'
  refute_line --partial 'would create label'
}

# ── stage 3: secret ──────────────────────────────────────────────────────

@test "apply sets the secret from --token-file without printing or logging it" {
  printf '%s\n' "$TOKEN_VALUE" >"$BATS_TEST_TMPDIR/token"
  extra_args=(--token-file "$BATS_TEST_TMPDIR/token")
  apply "" y y
  assert_success
  assert_equal "$(cat "$GH_SECRET_STDIN")" "$TOKEN_VALUE"
  grep -qx "secret set CLAUDE_CODE_OAUTH_TOKEN --repo $REPO" "$GH_LOG" || fail "gh secret set did not target $REPO"
  assert_line --partial 'set GitHub secret CLAUDE_CODE_OAUTH_TOKEN'
  assert_line --partial 'claude setup-token'
  assert_no_token_anywhere
}

@test "apply sets the secret from hidden entry without printing or logging it" {
  # banner, token, App, Dependabot
  apply "" "$TOKEN_VALUE" y y
  assert_success
  assert_equal "$(cat "$GH_SECRET_STDIN")" "$TOKEN_VALUE"
  assert_no_token_anywhere
}

@test "--token-file drops surrounding blanks and a CRLF line end" {
  printf '  %s \r\n\n' "$TOKEN_VALUE" >"$BATS_TEST_TMPDIR/token"
  extra_args=(--token-file "$BATS_TEST_TMPDIR/token")
  apply "" y y
  assert_success
  assert_equal "$(od -An -c "$GH_SECRET_STDIN")" "$(printf '%s' "$TOKEN_VALUE" | od -An -c)"
  assert_no_token_anywhere
}

@test "a --token-file with a second line exits 2, sets nothing and prints neither line" {
  printf '%s\nsecond-line-of-file\n' "$TOKEN_VALUE" >"$BATS_TEST_TMPDIR/token"
  extra_args=(--token-file "$BATS_TEST_TMPDIR/token")
  apply "" y y
  assert_failure 2
  [[ "$stderr" == *"a blank or a second line"* ]] || fail "stderr: $stderr"
  [[ "$output$stderr" != *second-line-of-file* ]] || fail "the file's content appeared in the output"
  [[ ! -e "$GH_SECRET_STDIN" ]] || fail "the secret was set"
  assert_no_token_anywhere
}

@test "a token without the sk-ant-oat prefix is set only after a confirmation" {
  local junk=not-a-claude-token
  # banner, token, set anyway? no
  apply "" "$junk" n
  assert_failure 2
  assert_line --partial 'does not start with sk-ant-oat'
  [[ ! -e "$GH_SECRET_STDIN" ]] || fail "the secret was set"
  [[ "$output$stderr" != *"$junk"* ]] || fail "the token appeared in the output"
  # banner, token, set anyway? yes, App, Dependabot
  apply "" "$junk" y y y
  assert_success
  assert_equal "$(cat "$GH_SECRET_STDIN")" "$junk"
}

@test "a failed gh secret set exits 4 without printing the token" {
  export GH_SECRET_SET_STATUS=1
  apply "" "$TOKEN_VALUE" y y
  assert_failure 4
  [[ "$stderr" == *"could not set secret CLAUDE_CODE_OAUTH_TOKEN"* ]] || fail "stderr: $stderr"
  assert_no_token_anywhere
}

@test "an existing secret is kept unless the maintainer confirms the replacement" {
  export GH_SECRETS=$'OTHER\nCLAUDE_CODE_OAUTH_TOKEN'
  # banner, replace? no, App, Dependabot
  apply "" n y y
  assert_success
  assert_line --partial 'Kept the existing secret.'
  run writes
  refute_line --partial 'secret set'
}

@test "dry run with --token-file names the file, never its content" {
  printf '%s\n' "$TOKEN_VALUE" >"$BATS_TEST_TMPDIR/token"
  run --separate-stderr "$WIZARD" --repo "$REPO" --token-file "$BATS_TEST_TMPDIR/token"
  assert_success
  assert_line --partial "[dry-run] would set secret CLAUDE_CODE_OAUTH_TOKEN from the file $BATS_TEST_TMPDIR/token"
  [[ ! -e "$GH_SECRET_STDIN" ]] || fail "dry run set the secret"
  assert_no_token_anywhere
}

@test "dry run with the secret present says --apply asks before replacing it" {
  export GH_SECRETS=CLAUDE_CODE_OAUTH_TOKEN
  run "$WIZARD" --repo "$REPO"
  assert_success
  assert_line --partial 'The secret exists. --apply asks before replacing it'
}

# ── stage 4: Actions allow-list ──────────────────────────────────────────

@test "an unrestricted Actions policy is left unchanged, in apply and dry run" {
  export GH_SECRETS=CLAUDE_CODE_OAUTH_TOKEN GH_ALLOWED_ACTIONS=all
  apply "" n y y
  assert_success
  assert_line --partial 'Allowed actions: all. Not restricted to a selected list,'
  assert_line --partial 'so the policy is left unchanged.'
  run writes
  refute_line --partial 'actions/permissions'
  run "$WIZARD" --repo "$REPO"
  assert_success
  assert_line --partial 'the policy is left unchanged.'
}

@test "apply adds the missing patterns and keeps the current ones and flags" {
  export GH_SECRETS=CLAUDE_CODE_OAUTH_TOKEN GH_ALLOWED_ACTIONS=selected
  export GH_SELECTED='{"github_owned_allowed":true,"verified_allowed":false,"patterns_allowed":["acme/tool@v1","actions/checkout@*"]}'
  apply "" n y y
  assert_success
  assert_line --partial 'allowed fabiandistler/agents/.github/workflows/*'
  refute_line --partial 'allowed actions/checkout@*'
  run python3 -c 'import json, sys; d = json.load(open(sys.argv[1])); print(d["github_owned_allowed"], d["verified_allowed"]); print("\n".join(d["patterns_allowed"]))' "$GH_PUT_BODY"
  assert_success
  assert_output "True False
acme/tool@v1
actions/checkout@*
fabiandistler/agents/.github/workflows/*
actions/setup-python@*
actions/upload-artifact@*
actions/download-artifact@*
anthropics/claude-code-action@*"
}

@test "dry run lists only the missing patterns of a selected list" {
  export GH_ALLOWED_ACTIONS=selected
  export GH_SELECTED='{"github_owned_allowed":false,"verified_allowed":false,"patterns_allowed":["actions/checkout@*"]}'
  run "$WIZARD" --repo "$REPO"
  assert_success
  assert_line --partial '[dry-run] would allow actions/setup-python@*'
  refute_line --partial '[dry-run] would allow actions/checkout@*'
  [[ ! -e "$GH_PUT_BODY" ]] || fail "dry run wrote the allow-list"
}

# ── stage 5: clicks ──────────────────────────────────────────────────────

@test "apply opens both pages and lists a click not confirmed as still to do" {
  export GH_SECRETS=CLAUDE_CODE_OAUTH_TOKEN
  # banner, keep secret, App yes, Dependabot no
  apply "" n y n
  assert_success
  assert_equal "$(cat "$BROWSER_LOG")" "https://github.com/$REPO/settings/installations
https://github.com/$REPO/settings/security_analysis"
  assert_line --partial 'Runner type → Standard GitHub runner'
  assert_line --partial 'Save runner selection'
  assert_line --partial "Dependabot runner type on $REPO"
  refute_line --partial "Claude GitHub App on $REPO"
}

@test "dry run shows the click paths without opening a browser" {
  run "$WIZARD" --repo "$REPO"
  assert_success
  assert_line --partial '"All repositories"'
  assert_line --partial "[dry-run] --apply opens https://github.com/$REPO/settings/security_analysis"
  [[ ! -e "$BROWSER_LOG" ]] || fail "dry run opened a browser"
}

# ── stage 6: verify ──────────────────────────────────────────────────────

@test "verify runs the onboarding check with the gh login's token and shows it" {
  run "$WIZARD" --repo "$REPO"
  assert_success
  assert_line --partial "check argv=--repo $REPO token=session-token"
  assert_line --partial 'No MISSING line.'
}

@test "MISSING lines from the check are pointed out; the wizard still ends 0" {
  export FAKE_CHECK_EXIT=1 GH_SECRETS=CLAUDE_CODE_OAUTH_TOKEN
  apply "" n y y
  assert_success
  assert_line --partial 'Act on every MISSING line above'
  assert_line --partial 'Setup complete'
}

# ── idempotency ──────────────────────────────────────────────────────────

@test "a re-run on a repo that is fully set up writes nothing" {
  export GH_LABELS="$ALL_LABELS" GH_SECRETS=CLAUDE_CODE_OAUTH_TOKEN
  export GH_ALLOWED_ACTIONS=selected GH_SELECTED="$FULL_SELECTED"
  apply "" n y y
  assert_success
  assert_line --partial 'already allows every factory pattern'
  assert_equal "$(writes)" ""
}
