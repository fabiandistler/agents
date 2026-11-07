#!/usr/bin/env bats
# Parity between the two readers of instruction fragments: the Bash installer
# (scripts/install/instructions.sh, scripts/install/claude-rules.sh) and the
# Python module scripts/instruction_fragments.py. install.sh must keep working
# without Python, so both readers stay; this suite proves they agree on every
# fragment the fragment gate accepts. Input the gate rejects (an empty
# `targets:`) is outside the contract and only checked against the gate.

load test_helper

setup() {
  common_setup
  OUT="$(mktemp -d)"
}

# Write a fixture fragment: $1 name, $2 frontmatter lines (without the ---).
make_fixture() {
  local dir="$1" name="$2" frontmatter="$3"
  mkdir -p "$dir"
  printf -- '---\n%s\n---\n\n\nRule text for %s.\n\nSecond paragraph.\n\n' \
    "$frontmatter" "$name" >"$dir/$name"
}

# Every format case the brief names, plus a path rule that excludes claude.
make_fixtures() {
  local dir="$1"
  make_fixture "$dir" 10-no-targets.md 'title: No targets'
  make_fixture "$dir" 11-targets-all.md $'title: All\ntargets: all'
  make_fixture "$dir" 12-single-target.md $'title: Single\ntargets: codex'
  make_fixture "$dir" 13-two-targets.md $'title: Two\ntargets: claude, opencode'
  make_fixture "$dir" 14-one-glob.md $'title: One glob\npaths: **/*.py'
  make_fixture "$dir" 15-several-globs.md \
    $'title: Several globs\ntargets: claude, codex\npaths: **/*.R, **/*.Rmd,  tests/**/*.R'
  make_fixture "$dir" 16-glob-not-claude.md $'title: Not claude\ntargets: codex, opencode\npaths: **/*.sh'
}

# Bash reader: for each fragment write <out>/bash/<name>/<field>.<target>.
# placement is none (not for this target), block, or rule (Claude path rule);
# rule.claude is the rendered rule file.
bash_reader() {
  local dir="$1" out="$2"
  (
    # shellcheck source=scripts/install/instructions.sh
    source "$REPO_ROOT/scripts/install/instructions.sh"
    # shellcheck source=scripts/install/claude-rules.sh
    source "$REPO_ROOT/scripts/install/claude-rules.sh"
    [[ -z "${BREAK_BASH_TARGETS:-}" ]] || fragment_matches_target() { return 0; }
    local file name target placement
    for file in "$dir"/*.md; do
      name="${file##*/}"
      mkdir -p "$out/bash/$name"
      for target in claude codex opencode; do
        placement=none
        if fragment_matches_target "$file" "$target"; then
          placement=block
          fragment_is_claude_rule "$file" "$target" && placement=rule
        fi
        printf '%s\n' "$placement" >"$out/bash/$name/placement.$target"
        if [[ "$placement" == rule ]]; then
          printf '%s\n' "$(render_claude_rule "$file")" >"$out/bash/$name/rule.$target"
        fi
      done
    done
  )
}

# Python reader: same layout under <out>/python/. Fails if a fragment does not
# pass the fragment gate, since only validated input is in the parity contract.
python_reader() {
  local dir="$1" out="$2" marker
  # The marker belongs to the installer; take it from there.
  marker="$(
    source "$REPO_ROOT/scripts/install/claude-rules.sh"
    claude_rule_marker
  )"
  "$PYTHON" - "$REPO_ROOT/scripts" "$dir" "$out/python" "$marker" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import instruction_fragments as fragments

out = Path(sys.argv[3])
marker = sys.argv[4]
for fragment in fragments.load_fragments(Path(sys.argv[2])):
    errors = fragments.validate_fragment(fragment)
    if errors:
        sys.exit(f"{fragment.name}: rejected by the fragment gate: {errors[0]}")
    folder = out / fragment.name
    folder.mkdir(parents=True)
    for target in ("claude", "codex", "opencode"):
        placement = "none"
        if fragments.fragment_matches_target(fragment, target):
            placement = "rule" if target == "claude" and fragment.path_globs else "block"
        (folder / f"placement.{target}").write_text(placement + "\n", encoding="utf-8")
        if placement == "rule":
            rule = fragments.render_claude_rule(fragment, marker)
            (folder / f"rule.{target}").write_text(rule.rstrip("\n") + "\n", encoding="utf-8")
PY
}

# Compare both readers field by field; name the fragment, field and target of
# every divergence.
compare_readers() {
  local out="$1" fragment name field divergent=0
  for fragment in "$out"/python/*/; do
    name="$(basename "$fragment")"
    for field in placement.claude placement.codex placement.opencode rule.claude; do
      if [[ ! -e "$out/python/$name/$field" && ! -e "$out/bash/$name/$field" ]]; then
        continue
      fi
      if ! diff -u "$out/python/$name/$field" "$out/bash/$name/$field" >"$out/diff" 2>&1; then
        printf 'parity: %s: field %s differs (python vs bash)\n' "$name" "$field"
        sed 's/^/  /' "$out/diff"
        divergent=1
      fi
    done
  done
  return "$divergent"
}

check_parity() {
  local dir="$1"
  python_reader "$dir" "$OUT" || return 1
  bash_reader "$dir" "$OUT" || return 1
  compare_readers "$OUT"
}

@test "both readers agree on every fragment in instructions/" {
  run check_parity "$REPO_ROOT/instructions"
  assert_success
  # Every fragment was compared, and the path-scoped R rule was rendered.
  local count
  count="$(find "$REPO_ROOT/instructions" -maxdepth 1 -name '*.md' | wc -l)"
  [[ "$(find "$OUT/python" -mindepth 1 -maxdepth 1 -type d | wc -l)" -eq "$count" ]] ||
    fail "not every fragment in instructions/ was compared"
  [[ -s "$OUT/bash/40-r.md/rule.claude" ]] || fail "40-r.md was not rendered as a Claude rule"
}

@test "both readers agree on the fixture fragments" {
  make_fixtures "$OUT/fixtures"
  run check_parity "$OUT/fixtures"
  assert_success
}

@test "fixtures resolve to the expected targets and placement" {
  # Guards the fixtures themselves: parity of two equally wrong readers
  # would otherwise pass.
  make_fixtures "$OUT/fixtures"
  bash_reader "$OUT/fixtures" "$OUT"
  local expected row targets=(claude codex opencode) i
  expected='
10-no-targets.md block block block
11-targets-all.md block block block
12-single-target.md none block none
13-two-targets.md block none block
14-one-glob.md rule block block
15-several-globs.md rule block none
16-glob-not-claude.md none block block'
  while read -r -a row; do
    ((${#row[@]})) || continue
    for i in 0 1 2; do
      [[ "$(cat "$OUT/bash/${row[0]}/placement.${targets[i]}")" == "${row[i + 1]}" ]] ||
        fail "${row[0]}: placement.${targets[i]} is not ${row[i + 1]}"
    done
  done <<<"$expected"
  assert_equal "$(cat "$OUT/bash/15-several-globs.md/rule.claude")" "$(
    printf -- '---\npaths:\n  - "**/*.R"\n  - "**/*.Rmd"\n  - "tests/**/*.R"\n'
    printf 'managed-by: fabiandistler/agents install.sh\n---\n\n'
    printf 'Rule text for 15-several-globs.md.\n\nSecond paragraph.'
  )"
}

@test "a broken Bash target filter fails parity and names the fragment" {
  make_fixtures "$OUT/fixtures"
  BREAK_BASH_TARGETS=1 run check_parity "$OUT/fixtures"
  assert_failure
  assert_output --partial 'parity: 12-single-target.md: field placement.claude differs'
  assert_output --partial 'parity: 13-two-targets.md: field placement.codex differs'
}

@test "an empty targets: is outside the contract: the fragment gate rejects it" {
  make_fixture "$OUT/empty" 10-empty-targets.md $'title: Empty\ntargets:   '
  run python_reader "$OUT/empty" "$OUT"
  assert_failure
  assert_output --partial "10-empty-targets.md: rejected by the fragment gate: 'targets' is empty"
}

@test "the Bash fragment reader never invokes python" {
  # install.sh must read fragments without Python: put failing python
  # stubs first on PATH and run the reader over every fragment.
  local stubs="$OUT/stubs"
  mkdir -p "$stubs"
  for py in python python3; do
    printf '#!/usr/bin/env bash\necho "%s called" >>"%s/calls"\nexit 127\n' \
      "$py" "$stubs" >"$stubs/$py"
    chmod +x "$stubs/$py"
  done
  make_fixtures "$OUT/fixtures"
  PATH="$stubs:$PATH" bash_reader "$REPO_ROOT/instructions" "$OUT/repo"
  PATH="$stubs:$PATH" bash_reader "$OUT/fixtures" "$OUT/fix"
  [[ ! -e "$stubs/calls" ]] || fail "the Bash fragment reader called $(cat "$stubs/calls")"
  # Static guard on the reader's own module as well: no python command word
  # (fragment names such as 30-python.md do not count).
  run grep -nE '(^|[^-_./[:alnum:]])python3?([[:space:]]|$)' "$REPO_ROOT/scripts/install/instructions.sh"
  assert_failure
  # And on the reader functions that live in claude-rules.sh.
  run bash -c 'source "$1/scripts/install/claude-rules.sh"; declare -f render_claude_rule claude_rule_marker claude_rule_dest' _ "$REPO_ROOT"
  assert_success
  refute_output --regexp '(^|[^-_./[:alnum:]])python3?([[:space:]]|$)'
}
