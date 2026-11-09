#!/usr/bin/env bats
# The bats-pre-push hook in .pre-commit-config.yaml runs only when a pushed
# file matches its `files:` filter. These tests pin which paths run the suites
# locally, check that every checkout path the suites and the install code name
# is covered, and that CI still runs the full Bats suite on every push.

load test_helper

setup() {
  common_setup
  CONFIG="$REPO_ROOT/.pre-commit-config.yaml"
}

# Print each argument that the bats-pre-push `files:` filter matches.
# prek matches `files:` with a regex search against repo-relative paths.
matching_paths() {
  "$PYTHON" - "$CONFIG" "$@" <<'PY'
import re
import sys

import yaml

config = yaml.safe_load(open(sys.argv[1]))
hooks = [h for repo in config["repos"] for h in repo["hooks"]]
(hook,) = [h for h in hooks if h["id"] == "bats-pre-push"]
assert not hook.get("always_run"), "bats-pre-push still has always_run"
pattern = re.compile(hook["files"])
for path in sys.argv[2:]:
    if pattern.search(path):
        print(path)
PY
}

@test "a push changing only maintenance reports skips the Bats suite" {
  run matching_paths maintenance/reports/2026-11-09-deps-audit.md \
    maintenance/README.md docs/install.md README.md AGENTS.md skills.json \
    .github/workflows/maintenance-gate.yml .claude/settings.json
  assert_success
  assert_output ''
}

@test "a push changing install.sh runs the Bats suite" {
  run matching_paths install.sh
  assert_success
  assert_output install.sh
}

@test "a push changing install-wizard.sh runs the Bats suite" {
  run matching_paths install-wizard.sh
  assert_success
  assert_output install-wizard.sh
}

@test "every checkout path the suites and install code name runs the suite" {
  # Collect each path written as $REPO_ROOT/<path> in the suites, the
  # installers and the install scripts they source.
  mapfile -t named < <(
    cd "$REPO_ROOT" &&
      grep -rhoE '\$\{?REPO_ROOT\}?/[A-Za-z0-9_./-]+' \
        test/*.bats test/*.bash install.sh install-wizard.sh scripts/install/ |
      sed -E 's#^\$\{?REPO_ROOT\}?/##' | sort -u
  )
  [ "${#named[@]}" -gt 0 ]
  paths=()
  for path in "${named[@]}"; do
    path="${path%/}"
    [ -n "$path" ] || continue
    # A directory stands for the files below it, which is what a push changes.
    if [ -d "$REPO_ROOT/$path" ]; then path="$path/file"; fi
    paths+=("$path")
  done
  run matching_paths "${paths[@]}"
  assert_success
  assert_output "$(printf '%s\n' "${paths[@]}")"
}

@test "the suites' own inputs run the Bats suite" {
  inputs=(.pre-commit-config.yaml .gitmodules .github/workflows/ci.yml
    test/install.bats test/bats/bats-core skills/repo-status/SKILL.md
    plugins/architecture/.claude-plugin/plugin.json
    instructions/20-coding-standards.md scripts/install/main.sh)
  run matching_paths "${inputs[@]}"
  assert_success
  assert_output "$(printf '%s\n' "${inputs[@]}")"
}

@test "CI runs the full Bats suite on every push and pull request" {
  ci="$REPO_ROOT/.github/workflows/ci.yml"
  run "$PYTHON" - "$ci" <<'PY'
import sys

import yaml

ci = yaml.safe_load(open(sys.argv[1]))
# PyYAML reads the bare key `on` as True.
triggers = ci.get("on", ci.get(True))
assert "push" in triggers and "pull_request" in triggers, triggers
steps = [s.get("run", "") for job in ci["jobs"].values() for s in job["steps"]]
assert any("scripts/check_all.sh --only bats" in run for run in steps), steps
PY
  assert_success
}
