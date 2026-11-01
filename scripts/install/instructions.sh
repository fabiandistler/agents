# shellcheck shell=bash
# Sourced by install.sh. Instruction fragments: the managed block and the on-demand payloads.

# --- Agent instruction files ------------------------------------------------
#
# instructions/*.md are single-topic rule fragments composed into one managed
# block inside each agent's global instruction file, so a rule is authored once
# instead of being copied by hand into every agent's config (which is how
# ~/.claude/CLAUDE.md and ~/.codex/AGENTS.md drifted apart in the first place).
# Ordering is the numeric filename prefix: glob order is already deterministic,
# so this needs no sort. Only --instructions turns any of this on.
#
# The block is marker-delimited like the Codex config blocks above, so whatever
# the user keeps outside it — an @-import, a machine-specific note — survives
# install, reinstall and uninstall untouched.
#
# opencode gets its own file. Its loader reads ~/.claude/CLAUDE.md only as a
# fallback when ~/.config/opencode/AGENTS.md does not exist, and opencode V2
# drops that fallback entirely (https://opencode.ai/docs/rules,
# https://opencode.ai/v2/docs/instructions). Its own file therefore never loads
# alongside CLAUDE.md, so no rule loads twice.
# Note the filenames differ per agent (CLAUDE.md vs AGENTS.md): the content is
# one AGENTS.md-style document, written to whatever each agent actually reads.

instructions_dir() { printf '%s/instructions' "$REPO_ROOT"; }

# --- On-demand instruction payloads ------------------------------------------
#
# Tier-C fragments (70, 80, 85) and Codex/opencode's Python baseline stay out of
# the always-loaded block: the block carries a one-line pointer, and the full
# text is installed under ~/.agents/instructions/. Each payload carries an
# ownership marker; a file without it is never touched.

instruction_payloads_dir() { printf '%s/.agents/instructions' "$HOME"; }

instruction_payload_marker() {
  printf '<!-- managed-by: fabiandistler/agents install.sh -->'
}

# A script payload cannot carry an HTML comment, so it uses a shell comment.
instruction_payload_marker_for() {
  case "$1" in
    *.py) printf '# managed-by: fabiandistler/agents install.sh' ;;
    *) instruction_payload_marker ;;
  esac
}

instruction_payload_dest() {
  printf '%s/%s' "$(instruction_payloads_dir)" "$1"
}

instruction_payload_source() {
  case "$1" in
    30-python.md) printf '%s/30-python.md' "$(instructions_dir)" ;;
    70-code-review-conventions.md) printf '%s/on-demand/70-code-review-conventions.md' "$(instructions_dir)" ;;
    80-agent-pipelines.md)
      printf '%s/skills/llm-application-engineering/references/agent-pipelines.md' "$REPO_ROOT"
      ;;
    85-agent-scripts.md) printf '%s/on-demand/85-agent-scripts.md' "$(instructions_dir)" ;;
    python_init_context.py) printf '%s/scripts/python_init_context.py' "$REPO_ROOT" ;;
    *) return 1 ;;
  esac
}

render_instruction_payload() {
  local name="$1" source
  source="$(instruction_payload_source "$name")" || return 1
  case "$name" in
    30-python.md)
      printf '%s\n\n' "$(instruction_payload_marker)"
      fragment_body "$source" | sed \
        '/^<!-- python-project-baseline:start -->$/d; /^<!-- python-project-baseline:end -->$/d'
      ;;
    python_init_context.py)
      printf '%s\n' "$(instruction_payload_marker_for "$name")"
      cat "$source"
      ;;
    *)
      printf '%s\n\n' "$(instruction_payload_marker)"
      cat "$source"
      ;;
  esac
}

instruction_payload_is_owned() {
  local dest
  dest="$(instruction_payload_dest "$1")"
  [[ -f "$dest" && ! -L "$dest" ]] || return 1
  grep -qxF "$(instruction_payload_marker_for "$1")" "$dest"
}

install_instruction_payload() {
  local name="$1" dest content
  dest="$(instruction_payload_dest "$name")"
  content="$(render_instruction_payload "$name")"
  owned_file_set "$dest" instruction-payload "$name" <<<"$content"
}

install_instruction_payloads() {
  local name
  for name in \
    30-python.md \
    70-code-review-conventions.md \
    80-agent-pipelines.md \
    85-agent-scripts.md; do
    install_instruction_payload "$name"
  done
  if target_is_selected claude; then
    install_instruction_payload python_init_context.py
  fi
}

# A pointer is rendered only when its payload is ours (or, in a dry run, would
# be): a foreign file at the payload path must not be advertised as the rules.
instruction_payload_available() {
  instruction_payload_is_owned "$1" && return 0
  if ((DRY_RUN)); then
    local dest
    dest="$(instruction_payload_dest "$1")"
    [[ ! -e "$dest" && ! -L "$dest" ]] && return 0
  fi
  return 1
}

# Reference checks only look inside installed instruction documents/settings.
# A target-specific uninstall keeps shared payloads while another target or
# the Claude uv-init hook still points at them.
instruction_payload_referenced() {
  local name="$1" target dest home_path
  dest="$(instruction_payload_dest "$name")"
  # The literal tilde is what composed instruction files contain, so no expansion.
  # shellcheck disable=SC2088
  home_path="~/.agents/instructions/$name"
  for target in claude codex opencode; do
    if ((UNINSTALL)) && target_is_selected "$target"; then
      continue
    fi
    local instructions_file
    instructions_file="$(instruction_file_for "$target")"
    if [[ -f "$instructions_file" ]] &&
      grep -qF "$(instructions_begin_marker)" "$instructions_file" &&
      { grep -qF "$dest" "$instructions_file" || grep -qF "$home_path" "$instructions_file"; }; then
      return 0
    fi
  done
  if [[ "$name" == "30-python.md" || "$name" == "python_init_context.py" ]] &&
    ! { ((UNINSTALL)) && target_is_selected claude; } &&
    [[ -f "$HOME/.claude/settings.json" ]] &&
    grep -qF "python_init_context.py" "$HOME/.claude/settings.json"; then
    return 0
  fi
  return 1
}

remove_instruction_payload() {
  local name="$1" dest
  dest="$(instruction_payload_dest "$name")"
  instruction_payload_is_owned "$name" || return 0
  if instruction_payload_referenced "$name"; then
    return 0
  fi
  if ((DRY_RUN)); then
    check_record all instruction-payload "$dest" stale
    printf '[dry-run] remove %s\n' "$dest"
    return 0
  fi
  rm "$dest"
  printf '  removed   %s\n' "$dest"
}

prune_instruction_payloads() {
  local name
  for name in \
    30-python.md \
    70-code-review-conventions.md \
    80-agent-pipelines.md \
    85-agent-scripts.md \
    python_init_context.py; do
    remove_instruction_payload "$name"
  done
}

target_is_selected() {
  local selected
  while IFS= read -r selected; do
    [[ "$selected" == "$1" ]] && return 0
  done < <(resolve_targets)
  return 1
}

rebase_owned_file_path() {
  local file="$1" marker="$2" before after current
  [[ -f "$file" && ! -L "$file" ]] || return 0
  grep -qxF "$marker" "$file" || return 0
  before="$(cat "$file")"
  after="${before//"$OLD_REPO_ROOT"/"$REPO_ROOT"}"
  [[ "$after" != "$before" ]] || return 0
  if ((DRY_RUN)); then
    printf '[dry-run] rewrite repo path in %s\n' "$file"
    return 0
  fi
  [[ -f "$file" && ! -L "$file" ]] || return 0
  current="$(cat "$file")"
  if [[ "$current" != "$before" ]] || ! grep -qxF "$marker" "$file"; then
    printf '  WARN      %s changed during --update; leaving it untouched\n' "$file" >&2
    return 0
  fi
  write_file_atomic "$file" "$after" "$marker" "" "$before" file
  printf '  updated   %s (moved checkout path)\n' "$file"
}

rebase_managed_block_path() {
  local file="$1" begin="$2" end="$3" before prefix remainder body suffix updated_body after current
  [[ -f "$file" && ! -L "$file" ]] || return 0
  before="$(cat "$file")"
  block_markers_balanced "$begin" "$end" <<<"$before" || return 0
  [[ "$(grep -Fxc "$begin" <<<"$before" || true)" == 1 ]] || return 0
  prefix="${before%%"$begin"*}"
  remainder="${before#*"$begin"}"
  body="${remainder%%"$end"*}"
  suffix="${remainder#*"$end"}"
  updated_body="${body//"$OLD_REPO_ROOT"/"$REPO_ROOT"}"
  [[ "$updated_body" != "$body" ]] || return 0
  after="$prefix$begin$updated_body$end$suffix"
  if ((DRY_RUN)); then
    printf '[dry-run] rewrite repo path in %s\n' "$file"
    return 0
  fi
  [[ -f "$file" && ! -L "$file" ]] || return 0
  current="$(cat "$file")"
  if [[ "$current" != "$before" ]] ||
    ! block_markers_balanced "$begin" "$end" <<<"$current" ||
    [[ "$(grep -Fxc "$begin" <<<"$current" || true)" != 1 ]]; then
    printf '  WARN      %s changed during --update; leaving it untouched\n' "$file" >&2
    return 0
  fi
  write_file_atomic "$file" "$after" "$begin" "$end" "$before" 1
  printf '  updated   %s (moved checkout path)\n' "$file"
}

# Global instruction file for a target. Unknown targets are an error.
instruction_file_for() {
  case "$1" in
    claude) printf '%s/.claude/CLAUDE.md' "$HOME" ;;
    codex) printf '%s/.codex/AGENTS.md' "$HOME" ;;
    opencode) printf '%s/.config/opencode/AGENTS.md' "$HOME" ;;
    *)
      echo "unknown target: $1" >&2
      return 1
      ;;
  esac
}

# Read a frontmatter field from a fragment. Prints the raw value, empty when
# the field is absent (same shape as skill_targets above).
instruction_field() {
  local file="$1" field="$2" line
  line="$(grep -m1 "^$field:" "$file" 2>/dev/null || true)"
  printf '%s' "${line#"$field":}"
}

# True if a fragment belongs in the given target's document. A fragment with no
# `targets:` field, or with `all`, belongs everywhere.
fragment_matches_target() {
  local file="$1" want="$2" targets t
  targets="$(instruction_field "$file" targets)"
  [[ -z "${targets//[[:space:]]/}" ]] && return 0
  local IFS=','
  for t in $targets; do
    t="${t//[[:space:]]/}"
    [[ "$t" == "all" || "$t" == "$want" ]] && return 0
  done
  return 1
}

# True if a fragment goes to Claude as a path-scoped rule instead of into the
# block: it has a `paths:` field and the target is claude. Claude Code loads a
# rule with `paths:` only once it reads a matching file; codex and opencode have
# no equivalent, so they keep the fragment in their block.
fragment_is_claude_rule() {
  local file="$1" want="$2" paths
  [[ "$want" == "claude" ]] || return 1
  paths="$(instruction_field "$file" paths)"
  [[ -n "${paths//[[:space:]]/}" ]]
}

# Fragment paths for a target's block, in filename order.
list_instruction_fragments() {
  local want="$1" file
  for file in "$(instructions_dir)"/*.md; do
    [[ -f "$file" ]] || continue
    fragment_matches_target "$file" "$want" || continue
    fragment_is_claude_rule "$file" "$want" && continue
    case "${file##*/}" in
      30-python.md)
        [[ "$want" == "claude" ]] || instruction_payload_available 30-python.md || continue
        ;;
      70-code-review-conventions.md)
        instruction_payload_available 70-code-review-conventions.md || continue
        ;;
      80-agent-pipelines.md)
        instruction_payload_available 80-agent-pipelines.md || continue
        ;;
      85-agent-scripts.md)
        instruction_payload_available 85-agent-scripts.md || continue
        ;;
    esac
    printf '%s\n' "$file"
  done
}

# Print a fragment without its YAML frontmatter, with leading and trailing
# blank lines trimmed so the composed block has predictable spacing.
fragment_body() {
  awk '
    NR == 1 && $0 == "---" { fm = 1; next }
    fm && $0 == "---" { fm = 0; next }
    fm { next }
    $0 == "" { if (printed) pending++; next }
    { while (pending) { print ""; pending-- } print; printed = 1 }
  ' "$1"
}

# Compose the fragment paths read on stdin into one document, one blank line
# between fragments.
render_instructions() {
  local target="$1" file first=1
  while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    ((first)) || printf '\n'
    first=0
    if [[ "$target" != "claude" && "${file##*/}" == "30-python.md" ]]; then
      printf 'For Python work, read `%s`.\n' \
        "$(instruction_payload_dest 30-python.md)"
    else
      fragment_body "$file"
    fi
  done
}

instructions_begin_marker() {
  printf '<!-- >>> agents instructions (managed by install.sh, do not edit) >>> -->'
}

instructions_end_marker() {
  printf '<!-- <<< agents instructions <<< -->'
}

# Compose the fragments for a target and write them into its instruction file
# as the managed block, replacing whatever the block held before. Content
# outside the markers is preserved; unbalanced markers leave the file alone.
install_instructions() {
  local target="$1" dest
  dest="$(instruction_file_for "$target")" || return 1
  local fragments count=0 file
  fragments="$(list_instruction_fragments "$target")"
  while IFS= read -r file; do
    if [[ -n "$file" ]]; then
      count=$((count + 1))
    fi
  done <<<"$fragments"
  if ((count == 0)); then
    printf '  WARN      no instruction fragments match target %s (skipping %s)\n' \
      "$target" "$dest" >&2
    return 0
  fi
  managed_block_set "$dest" "$(instructions_begin_marker)" "$(instructions_end_marker)" \
    "$(render_instructions "$target" <<<"$fragments")" "$count instruction fragments"
}
