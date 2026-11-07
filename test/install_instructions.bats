#!/usr/bin/env bats
# install.sh --instructions: the managed instruction blocks, on-demand
# payloads, and path-scoped Claude rules.

load install_helper

setup() {
  install_setup
}

# A HOME whose CLAUDE.md has hand-written content, saved as claude-before.md.
make_instructions_home() {
  HOME_INS="$(mktemp -d)"
  mkdir -p "$HOME_INS/.claude" "$HOME_INS/.codex"
  printf 'my own notes\n\n@RTK.md\n' >"$HOME_INS/.claude/CLAUDE.md"
  cp "$HOME_INS/.claude/CLAUDE.md" "$HOME_INS/claude-before.md"
  CLAUDE_MD="$HOME_INS/.claude/CLAUDE.md"
}

@test "instructions are not touched without --instructions" {
  # --instructions composes instructions/ into each agent's global file,
  # inside the managed markers only. Without the flag nothing is written.
  make_instructions_home
  HOME="$HOME_INS" "$INSTALL" --target=claude --category=communication >/dev/null
  diff -q "$HOME_INS/claude-before.md" "$HOME_INS/.claude/CLAUDE.md" >/dev/null ||
    fail "instructions written without --instructions"
  [[ ! -e "$HOME_INS/.agents/instructions" ]] || fail "instruction payloads written without --instructions"
  [[ ! -e "$HOME_INS/.claude/settings.json" ]] || fail "Claude hook written without --instructions"
}

@test "instructions block installs once and is idempotent" {
  # With the flag the block lands, hand-written content survives, and a
  # second run is a no-op (idempotent).
  make_instructions_home
  HOME="$HOME_INS" "$INSTALL" --target=claude --category=communication --instructions >/dev/null
  grep -q '^my own notes$' "$CLAUDE_MD" || fail "hand-written line lost"
  grep -q '^@RTK.md$' "$CLAUDE_MD" || fail "@-import lost"
  grep -q 'agents instructions (managed by install.sh' "$CLAUDE_MD" || fail "begin marker missing"
  grep -q '<!-- <<< agents instructions <<< -->' "$CLAUDE_MD" || fail "end marker missing"
  ! grep -q 'Use uv for Python package development' "$CLAUDE_MD" ||
    fail "path-scoped Python fragment stayed in Claude's always-on block"
  PYTHON_RULE="$HOME_INS/.claude/rules/agents-30-python.md"
  [[ -f "$PYTHON_RULE" ]] || fail "path-scoped Python rule was not written"
  grep -q '"\*\*/\*.py"' "$PYTHON_RULE" || fail "Python rule lacks its quoted paths glob"
  grep -q 'New project baseline' "$PYTHON_RULE" || fail "Python rule has no baseline"
  [[ -f "$HOME_INS/.agents/instructions/30-python.md" ]] || fail "Python baseline payload missing"
  [[ -f "$HOME_INS/.agents/instructions/70-code-review-conventions.md" ]] || fail "code review payload missing"
  [[ -f "$HOME_INS/.agents/instructions/80-agent-pipelines.md" ]] || fail "agent pipeline payload missing"
  [[ -f "$HOME_INS/.agents/instructions/85-agent-scripts.md" ]] || fail "agent scripts payload missing"
  grep -Fq '.agents/instructions/70-code-review-conventions.md' "$CLAUDE_MD" ||
    fail "Claude block lacks the code review pointer"
  [[ -f "$HOME_INS/.agents/instructions/python_init_context.py" ]] || fail "Python hook command missing"
  "$PYTHON" - "$HOME_INS/.claude/settings.json" <<'PY' || fail "Claude uv-init hook missing"
import json, sys
settings = json.load(open(sys.argv[1], encoding="utf-8"))
handlers = [h for group in settings["hooks"]["PreToolUse"] for h in group["hooks"]]
entry = next(h for h in handlers if h.get("if") == "Bash(uv init*)")
assert "python_init_context.py" in entry["command"]
PY
  hook_output="$(printf '%s' '{"tool_name":"Bash","tool_input":{"command":"uv init --package demo"}}' |
    (cd /tmp && HOME="$HOME_INS" "$PYTHON" "$HOME_INS/.agents/instructions/python_init_context.py"))"
  grep -q 'New project baseline' <<<"$hook_output" || fail "installed uv-init hook did not inject the Python baseline"
  cp "$CLAUDE_MD" "$HOME_INS/claude-once.md"
  cp "$HOME_INS/.claude/settings.json" "$HOME_INS/settings-once.json"
  HOME="$HOME_INS" "$INSTALL" --target=claude --category=communication --instructions >/dev/null
  diff -q "$HOME_INS/claude-once.md" "$CLAUDE_MD" >/dev/null ||
    fail "second --instructions run changed the file"
  diff -q "$HOME_INS/settings-once.json" "$HOME_INS/.claude/settings.json" >/dev/null ||
    fail "second --instructions run changed Claude settings"
}

@test "instructions uninstall removes only the managed block" {
  # --uninstall strips only our block, restoring the file byte for byte.
  make_instructions_home
  HOME="$HOME_INS" "$INSTALL" --target=claude --category=communication --instructions >/dev/null
  HOME="$HOME_INS" "$INSTALL" --target=claude --category=communication --instructions --uninstall >/dev/null
  diff -q "$HOME_INS/claude-before.md" "$CLAUDE_MD" >/dev/null ||
    fail "uninstall did not restore the original instruction file"
  [[ ! -e "$HOME_INS/.agents/instructions/30-python.md" ]] || fail "uninstall left the Python payload"
  [[ ! -e "$HOME_INS/.agents/instructions/python_init_context.py" ]] || fail "uninstall left the Python hook command"
  ! grep -q python_init_context.py "$HOME_INS/.claude/settings.json" ||
    fail "uninstall left the Claude uv-init hook"
}

@test "instructions create codex's and opencode's own files" {
  # codex and opencode each get their own file created from nothing
  # (opencode reads ~/.claude/CLAUDE.md only as a fallback, V2 not at all),
  # and --uninstall strips the block from both.
  HOME_INS2="$(mktemp -d)"
  HOME="$HOME_INS2" "$INSTALL" --target=all --category=communication --instructions >/dev/null
  for f in .codex/AGENTS.md .config/opencode/AGENTS.md; do
    [[ -f "$HOME_INS2/$f" ]] || fail "$f was not created"
    grep -q 'For Python work, read' "$HOME_INS2/$f" ||
      fail "$f has no Python baseline pointer"
    ! grep -q 'Use uv for Python package development' "$HOME_INS2/$f" ||
      fail "$f loaded the Python baseline inline"
  done
  grep -q 'Use uv for Python package development' "$HOME_INS2/.agents/instructions/30-python.md" ||
    fail "Codex/opencode Python pointer has no installed target"
  HOME="$HOME_INS2" "$INSTALL" --target=opencode --category=communication --instructions --uninstall >/dev/null
  ! grep -q 'agents instructions' "$HOME_INS2/.config/opencode/AGENTS.md" ||
    fail "opencode uninstall left the instructions block"
  [[ -f "$HOME_INS2/.agents/instructions/80-agent-pipelines.md" ]] ||
    fail "target-specific uninstall removed a payload still used by codex and claude"
}

@test "foreign payload files are left alone and not pointed at" {
  # A foreign file at a payload path is never overwritten, and the block
  # leaves out the pointer to it.
  HOME_INS5="$(mktemp -d)"
  mkdir -p "$HOME_INS5/.agents/instructions"
  printf 'mine\n' >"$HOME_INS5/.agents/instructions/85-agent-scripts.md"
  HOME="$HOME_INS5" "$INSTALL" --target=codex --category=communication --instructions >/dev/null 2>&1
  [[ "$(cat "$HOME_INS5/.agents/instructions/85-agent-scripts.md")" == mine ]] ||
    fail "install overwrote a foreign payload file"
  ! grep -q '85-agent-scripts.md' "$HOME_INS5/.codex/AGENTS.md" ||
    fail "block points at a foreign payload file"
  grep -q '70-code-review-conventions.md' "$HOME_INS5/.codex/AGENTS.md" ||
    fail "block lost the pointer to an owned payload"
  HOME="$HOME_INS5" "$INSTALL" --target=codex --category=communication --instructions --uninstall >/dev/null 2>&1
  [[ -f "$HOME_INS5/.agents/instructions/85-agent-scripts.md" ]] || fail "uninstall removed a foreign payload file"
  [[ ! -e "$HOME_INS5/.agents/instructions/70-code-review-conventions.md" ]] ||
    fail "uninstall left an unreferenced owned payload"
}

@test "unbalanced markers and dry-run never write instruction files" {
  # Unbalanced markers (a hand edit) leave the file completely alone, and
  # --dry-run never writes.
  HOME_INS3="$(mktemp -d)"
  mkdir -p "$HOME_INS3/.claude"
  printf 'notes\n\n<!-- >>> agents instructions (managed by install.sh, do not edit) >>> -->\nstray\n' \
    >"$HOME_INS3/.claude/CLAUDE.md"
  cp "$HOME_INS3/.claude/CLAUDE.md" "$HOME_INS3/unbalanced-before.md"
  HOME="$HOME_INS3" "$INSTALL" --target=claude --category=communication --instructions >/dev/null 2>&1
  diff -q "$HOME_INS3/unbalanced-before.md" "$HOME_INS3/.claude/CLAUDE.md" >/dev/null ||
    fail "unbalanced markers did not protect the file"
  HOME_INS4="$(mktemp -d)"
  ins_dry_output="$(HOME="$HOME_INS4" "$INSTALL" --target=codex --category=communication --instructions --dry-run 2>&1)"
  [[ ! -e "$HOME_INS4/.codex/AGENTS.md" ]] || fail "dry-run wrote an instruction file"
  grep -Fq "[dry-run] write $HOME_INS4/.codex/AGENTS.md" <<<"$ins_dry_output" ||
    fail "dry-run did not report the instruction block write"
}

@test "paths: fragments become path-scoped Claude rules only" {
  # A fragment with `paths:` leaves Claude's block for a path-scoped rule
  # under ~/.claude/rules/ (codex and opencode keep R inline and use the
  # Python pointer), a foreign rule file is never touched, and --uninstall
  # removes only ours.
  HOME_RULE_DRY="$(mktemp -d)"
  RULE_DRY_PATH="$HOME_RULE_DRY/.claude/rules/agents-40-r.md"
  rule_dry_output="$(HOME="$HOME_RULE_DRY" "$INSTALL" --target=all --category=communication --instructions --dry-run 2>&1)"
  [[ "$(grep -Fc "[dry-run] write $RULE_DRY_PATH" <<<"$rule_dry_output")" -eq 1 ]] ||
    fail "dry-run did not report the Claude rule write exactly once"
  [[ ! -d "$HOME_RULE_DRY/.claude/rules" ]] ||
    fail "dry-run created the Claude rules directory"

  HOME_RULES="$(mktemp -d)"
  mkdir -p "$HOME_RULES/.claude/rules"
  printf 'mine\n' >"$HOME_RULES/.claude/rules/own.md"
  HOME="$HOME_RULES" "$INSTALL" --target=all --category=communication --instructions >/dev/null
  R_RULE="$HOME_RULES/.claude/rules/agents-40-r.md"
  [[ -f "$R_RULE" ]] || fail "path-scoped R rule was not written"
  grep -qxF '  - "**/*.R"' "$R_RULE" || fail "R rule lacks its quoted paths glob"
  grep -q 'Namespace' "$R_RULE" || fail "R rule has no fragment body"
  ! grep -q 'Namespace' "$HOME_RULES/.claude/CLAUDE.md" ||
    fail "path-scoped fragment still inside Claude's block"
  for f in .codex/AGENTS.md .config/opencode/AGENTS.md; do
    grep -q 'Namespace' "$HOME_RULES/$f" || fail "$f lost the path-scoped fragment"
    grep -q 'For Python work, read' "$HOME_RULES/$f" || fail "$f lost the Python pointer"
    ! grep -q 'Use uv for Python package development' "$HOME_RULES/$f" ||
      fail "$f loaded the Python baseline inline"
  done
  rule_content_before="$(cat "$R_RULE")"
  rule_inode_before="$(file_inode "$R_RULE")"
  rule_output="$(HOME="$HOME_RULES" "$INSTALL" --target=all --category=communication --instructions 2>&1)"
  [[ "$(cat "$R_RULE")" == "$rule_content_before" ]] ||
    fail "reinstall changed an unchanged Claude rule"
  [[ "$(file_inode "$R_RULE")" == "$rule_inode_before" ]] ||
    fail "reinstall rewrote an unchanged Claude rule"
  grep -q '  ok .*agents-40-r.md' <<<"$rule_output" ||
    fail "reinstall did not report the unchanged Claude rule as ok"
  HOME="$HOME_RULES" "$INSTALL" --target=claude --category=communication --instructions --uninstall >/dev/null 2>&1
  [[ ! -e "$R_RULE" ]] || fail "uninstall left the managed R rule"
  [[ -f "$HOME_RULES/.agents/instructions/80-agent-pipelines.md" ]] ||
    fail "Claude uninstall removed a payload still used by codex and opencode"
  [[ -f "$HOME_RULES/.claude/rules/own.md" ]] || fail "uninstall removed a foreign rule file"
}
