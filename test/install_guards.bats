#!/usr/bin/env bats
# install.sh --merge-guard and --secret-guard, and the Claude guard plugins.

load install_helper

setup() {
  install_setup
}

@test "--merge-guard installs per agent, idempotently, and uninstalls cleanly" {
  # --merge-guard puts the PR merge guard into each agent's user-level config
  # (Codex [hooks] block, opencode plugin link, Claude plugin through the claude
  # CLI), keeps foreign settings, is idempotent, and --uninstall restores the
  # files and removes the plugin.
  HOME_MG="$(mktemp -d)"
  mkdir -p "$HOME_MG/.claude" "$HOME_MG/.codex"
  printf '{"model": "opus", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]}}\n' \
    >"$HOME_MG/.claude/settings.json"
  cp "$HOME_MG/.claude/settings.json" "$HOME_MG/claude-before.json"
  printf 'model = "o3"\n' >"$HOME_MG/.codex/config.toml"
  cp "$HOME_MG/.codex/config.toml" "$HOME_MG/codex-before.toml"
  HOME="$HOME_MG" "$INSTALL" --target=all --category=communication >/dev/null
  ! grep -q pr_merge_guard "$HOME_MG/.claude/settings.json" "$HOME_MG/.codex/config.toml" ||
    fail "merge guard installed without --merge-guard"
  mg_calls="$(claude_stub_dir "$HOME_MG")/calls"
  [[ ! -s "$mg_calls" ]] || fail "install without --merge-guard called the claude CLI"
  mg_output="$(HOME="$HOME_MG" "$INSTALL" --target=all --category=communication --merge-guard)"
  grep -Fq 'installed merge-guard@fabiandistler-agents' <<<"$mg_output" ||
    fail "--merge-guard did not report the Claude plugin install: $mg_output"
  [[ "$(grep -c '^plugin \(install\|marketplace add\)' "$mg_calls")" -eq 2 ]] &&
    grep -Fxq 'plugin marketplace add fabiandistler/agents' "$mg_calls" &&
    grep -Fxq 'plugin install merge-guard@fabiandistler-agents' "$mg_calls" ||
    fail "--merge-guard did not add the marketplace and install the plugin once: $(cat "$mg_calls")"
  diff -q "$HOME_MG/claude-before.json" "$HOME_MG/.claude/settings.json" >/dev/null ||
    fail "--merge-guard wrote into ~/.claude/settings.json"
  "$PYTHON" - "$HOME_MG" <<'PY' || fail "merge guard entries missing or foreign settings lost"
import sys, tomllib
home = sys.argv[1]
codex = tomllib.load(open(f"{home}/.codex/config.toml", "rb"))
assert codex["model"] == "o3"
assert "--harness codex" in codex["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
PY
  [[ -L "$HOME_MG/.config/opencode/plugins/pr-merge-guard.js" ]] || fail "opencode plugin not linked"
  cp "$HOME_MG/.codex/config.toml" "$HOME_MG/codex-once.toml"
  HOME="$HOME_MG" "$INSTALL" --target=all --category=communication --merge-guard >/dev/null
  diff -q "$HOME_MG/codex-once.toml" "$HOME_MG/.codex/config.toml" >/dev/null ||
    fail "second --merge-guard run changed config.toml"
  [[ "$(grep -c '^plugin \(install\|marketplace add\)' "$mg_calls")" -eq 2 ]] ||
    fail "second --merge-guard run installed the Claude plugin again"
  HOME="$HOME_MG" "$INSTALL" --target=all --category=communication --merge-guard --uninstall >/dev/null
  grep -Fxq 'plugin uninstall merge-guard@fabiandistler-agents' "$mg_calls" ||
    fail "--merge-guard --uninstall did not remove the Claude plugin"
  diff -q "$HOME_MG/claude-before.json" "$HOME_MG/.claude/settings.json" >/dev/null ||
    fail "uninstall changed a settings.json without our entry"
  diff -q "$HOME_MG/codex-before.toml" "$HOME_MG/.codex/config.toml" >/dev/null ||
    fail "uninstall did not restore config.toml"
  [[ ! -e "$HOME_MG/.config/opencode/plugins/pr-merge-guard.js" ]] || fail "uninstall left the plugin"
}

@test "--secret-guard installs next to the merge guard and uninstalls on its own" {
  # --secret-guard installs next to --merge-guard: two Codex hook entries in
  # one valid config.toml, its own opencode link and Claude plugin, idempotent,
  # and --secret-guard --uninstall leaves the merge guard in place.
  HOME_SG="$(mktemp -d)"
  mkdir -p "$HOME_SG/.codex"
  printf 'model = "o3"\n' >"$HOME_SG/.codex/config.toml"
  HOME="$HOME_SG" "$INSTALL" --target=all --category=communication --merge-guard >/dev/null
  cp "$HOME_SG/.codex/config.toml" "$HOME_SG/merge-only.toml"
  sg_output="$(HOME="$HOME_SG" "$INSTALL" --target=all --category=communication \
    --merge-guard --secret-guard)"
  grep -Fq 'installed secret-guard@fabiandistler-agents' <<<"$sg_output" &&
    grep -Fq 'ok        merge-guard@fabiandistler-agents' <<<"$sg_output" ||
    fail "--secret-guard did not install the Claude plugin next to the merge guard: $sg_output"
  sg_stub="$(claude_stub_dir "$HOME_SG")"
  [[ "$(grep -c '^plugin marketplace add' "$sg_stub/calls")" -eq 1 ]] ||
    fail "the second guard added the marketplace again"
  "$PYTHON" - "$HOME_SG" <<'PY' || fail "secret guard entry missing next to the merge guard"
import sys, tomllib
codex = tomllib.load(open(f"{sys.argv[1]}/.codex/config.toml", "rb"))
commands = [e["hooks"][0]["command"] for e in codex["hooks"]["PreToolUse"]]
assert [c.split("/")[-1] for c in commands] == [
    'pr_merge_guard.py" --harness codex', 'secret_read_guard.py" --harness codex'
], commands
PY
  [[ -L "$HOME_SG/.config/opencode/plugins/secret-read-guard.js" ]] ||
    fail "opencode secret guard plugin not linked"
  cp "$HOME_SG/.codex/config.toml" "$HOME_SG/both.toml"
  HOME="$HOME_SG" "$INSTALL" --target=all --category=communication --merge-guard --secret-guard >/dev/null
  diff -q "$HOME_SG/both.toml" "$HOME_SG/.codex/config.toml" >/dev/null ||
    fail "second --secret-guard run changed config.toml"
  HOME="$HOME_SG" "$INSTALL" --target=all --category=communication --secret-guard --uninstall >/dev/null
  diff -q "$HOME_SG/merge-only.toml" "$HOME_SG/.codex/config.toml" >/dev/null ||
    fail "--secret-guard --uninstall did not leave just the merge guard"
  [[ ! -e "$HOME_SG/.config/opencode/plugins/secret-read-guard.js" ]] ||
    fail "uninstall left the secret guard plugin"
  [[ -L "$HOME_SG/.config/opencode/plugins/pr-merge-guard.js" ]] ||
    fail "--secret-guard --uninstall removed the merge guard plugin"
  [[ "$(cat "$sg_stub/installed")" == 'merge-guard@fabiandistler-agents' ]] ||
    fail "--secret-guard --uninstall did not leave just the Claude merge-guard plugin"
}

@test "Claude guard plugins: dry run, check, disabled and project-scope plugins" {
  home="$(mktemp -d)"
  stub="$(claude_stub_dir "$home")"
  run_install "$home" --target=claude --secret-guard --dry-run
  [[ "$status" -eq 0 ]] || fail "dry run failed: $output"
  [[ "$output" == *'[dry-run] claude plugin marketplace add fabiandistler/agents'* &&
    "$output" == *'[dry-run] claude plugin install secret-guard@fabiandistler-agents'* ]] ||
    fail "dry run did not plan the marketplace and plugin install: $output"
  ! grep -Ev -- '--json$' "$stub/calls" || fail "dry run called a mutating claude command"
  report="$home/check.tsv"
  run_install "$home" --target=claude --secret-guard --check --output "$report"
  [[ "$status" -eq 3 ]] || fail "--check missed the absent plugin: $output"
  grep -Fqx $'claude\tsecret-guard\tsecret-guard@fabiandistler-agents\tmissing' "$report" ||
    fail "--check did not report the absent plugin as missing"
  # A disabled plugin stays disabled; a project-scope one does not count.
  echo fabiandistler-agents >"$stub/marketplaces"
  echo merge-guard@fabiandistler-agents >"$stub/disabled"
  echo secret-guard@fabiandistler-agents >"$stub/project"
  run_install "$home" --target=claude --merge-guard --secret-guard
  [[ "$status" -eq 0 ]] || fail "install with a disabled plugin failed: $output"
  [[ "$output" == *'merge-guard@fabiandistler-agents is disabled in Claude Code'* ]] ||
    fail "install did not warn about the disabled plugin: $output"
  ! grep -Fxq 'plugin install merge-guard@fabiandistler-agents' "$stub/calls" ||
    fail "install turned the disabled plugin back on"
  grep -Fxq 'plugin install secret-guard@fabiandistler-agents' "$stub/calls" ||
    fail "a project-scope plugin kept the user-scope install from running"
  ! grep -Fq 'marketplace add' "$stub/calls" || fail "install added a marketplace Claude knows"
  run_install "$home" --target=claude --merge-guard --secret-guard --check --output "$report"
  [[ "$status" -eq 3 ]] || fail "--check passed with a disabled plugin: $output"
  [[ "$(grep -c $'\tmissing$' "$report")" -eq 1 ]] &&
    grep -Fqx $'claude\tmerge-guard\tmerge-guard@fabiandistler-agents\tmissing' "$report" ||
    fail "--check did not report just the disabled plugin: $(cat "$report")"
  : >"$stub/disabled"
  echo merge-guard@fabiandistler-agents >>"$stub/installed"
  run_install "$home" --target=claude --merge-guard --secret-guard --check
  [[ "$status" -eq 0 && "$output" == '--check: clean' ]] ||
    fail "--check with both plugins enabled was not clean: $output"
}

@test "Claude guard plugins: a failing claude CLI aborts, a missing one warns" {
  home="$(mktemp -d)"
  echo 'plugin install secret-guard@fabiandistler-agents' >"$(claude_stub_dir "$home")/fail"
  run_install "$home" --target=claude --secret-guard
  [[ "$status" -ne 0 && "$output" == *'claude stub: failing on request'* ]] ||
    fail "a failed plugin install did not abort install.sh: $status $output"
  [[ ! -e "$XDG_STATE_HOME/fabiandistler-agents/install.json" ]] ||
    fail "a failed plugin install still saved the install state"
  no_cli_home="$(mktemp -d)"
  run env HOME="$no_cli_home" PATH="$(path_without_claude)" "$INSTALL" --target=claude --secret-guard
  [[ "$status" -eq 0 ]] || fail "install without the claude CLI failed: $output"
  [[ "$output" == *'claude CLI not found; install the secret read guard with: claude plugin install secret-guard@fabiandistler-agents'* ]] ||
    fail "install without the claude CLI did not name the manual command: $output"
  run env HOME="$no_cli_home" PATH="$(path_without_claude)" "$INSTALL" --target=claude --secret-guard --uninstall
  [[ "$status" -eq 0 && "$output" == *'claude plugin uninstall secret-guard@fabiandistler-agents'* ]] ||
    fail "uninstall without the claude CLI did not name the manual command: $output"
}
