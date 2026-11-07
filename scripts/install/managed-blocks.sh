# shellcheck shell=bash
# Sourced by install.sh. Owned files and marker-delimited blocks, written atomically.

# --- Managed blocks ----------------------------------------------------------
#
# A managed block is a marker-delimited region install.sh owns inside a file it
# does not (see GLOSSARY.md). Each caller passes its own begin and end marker
# lines verbatim, so blocks written by earlier versions keep matching. Content
# outside the markers is never touched. A file whose markers are unbalanced (a
# hand edit) is left alone: stripping from a dangling begin marker would drop
# everything after it. `what` names the block's content in the status lines.

# Replace a file with the given content, atomically. A plain `> "$path"`
# truncates before writing, so an interrupt in between leaves a file we do not
# own in pieces; a temp file plus mv either lands whole or not at all.
write_file_atomic() {
  local path="$1" content="$2" owner_marker="${3:-}" owner_end="${4:-}" mode="${7:-}"
  local expected_before="${5-}" expected_count="${6-}" expected_count_set=0 current current_count
  local tmp="$path.tmp.$$"
  (($# < 6)) || expected_count_set=1
  if [[ -e "$tmp" || -L "$tmp" ]]; then
    printf 'refusing to replace temporary write path: %s\n' "$tmp" >&2
    return 1
  fi
  if [[ -n "$content" ]]; then
    printf '%s\n' "$content" >"$tmp"
  else
    : >"$tmp"
  fi
  [[ -z "$mode" ]] || chmod "$mode" "$tmp"
  if ((UPDATE_MODE)) && [[ -n "$owner_marker" ]]; then
    if [[ -L "$path" ]] || { [[ -e "$path" ]] && [[ ! -f "$path" ]]; }; then
      rm "$tmp"
      printf '  WARN      %s is no longer a regular managed file; leaving it untouched\n' "$path" >&2
      return 0
    fi
    if [[ -f "$path" ]]; then
      current="$(cat "$path")"
      if ((expected_count_set)); then
        if [[ -n "$owner_end" ]]; then
          current_count="$(grep -Fxc "$owner_marker" <<<"$current" || true)"
          if [[ "$current" != "$expected_before" ]] ||
            ! block_markers_balanced "$owner_marker" "$owner_end" <<<"$current" ||
            [[ "$current_count" != "$expected_count" ]]; then
            rm "$tmp"
            printf '  WARN      %s changed during --update; leaving it untouched\n' "$path" >&2
            return 0
          fi
        elif [[ "$current" != "$expected_before" ]] || ! grep -qxF "$owner_marker" "$path"; then
          rm "$tmp"
          printf '  WARN      %s changed during --update; leaving it untouched\n' "$path" >&2
          return 0
        fi
      elif ! grep -qxF "$owner_marker" "$path"; then
        rm "$tmp"
        printf '  WARN      %s lost its ownership marker during --update; leaving it untouched\n' "$path" >&2
        return 0
      fi
    elif ((expected_count_set)) && [[ -n "$expected_before" ]]; then
      rm "$tmp"
      printf '  WARN      %s disappeared during --update; leaving it untouched\n' "$path" >&2
      return 0
    fi
  fi
  mv "$tmp" "$path"
}

# Set a complete file this installer owns. The caller renders content and
# sends it on stdin; this function guards ownership and writes only changes.
# The label names the kind of file and selects its ownership marker; `name`
# picks the marker for instruction payloads, which differ by file type.
owned_file_set() {
  local target="$1" label="$2" name="${3:-}" marker kind check_target content current_before
  case "$label" in
    agent)
      marker="$AGENT_MARKER" kind=codex-agent check_target=codex
      ;;
    opencode-agent)
      marker="$AGENT_MARKER" kind=opencode-agent check_target=opencode
      ;;
    rule)
      marker="$(claude_rule_marker)" kind=claude-rule check_target=claude
      ;;
    instruction-payload)
      marker="$(instruction_payload_marker_for "$name")" kind=instruction-payload
      check_target="$CHECK_CURRENT_TARGET"
      ;;
    *)
      printf 'owned_file_set: unknown label %s\n' "$label" >&2
      return 2
      ;;
  esac
  content="$(cat)"
  if [[ -L "$target" ]] || { [[ -e "$target" ]] && [[ ! -f "$target" ]]; } ||
    { [[ -e "$target" ]] && ! grep -qxF "$marker" "$target" 2>/dev/null; }; then
    check_record "$check_target" "$kind" "$target" foreign
    ((CHECK_MODE)) ||
      printf '  WARN      %s exists and is not managed by install.sh (leaving it untouched)\n' \
        "$target" >&2
    return 0
  fi
  if ((CHECK_MODE)); then
    if [[ ! -f "$target" ]]; then
      check_record "$check_target" "$kind" "$target" missing
    elif [[ "$(cat "$target")" != "$content" ]]; then
      check_record "$check_target" "$kind" "$target" stale
    fi
    return 0
  fi
  if [[ -f "$target" && "$(cat "$target")" == "$content" ]]; then
    printf '  ok        %s (%s)\n' "$target" "$label"
    return 0
  fi
  if ((DRY_RUN)); then
    printf '[dry-run] write %s\n' "$target"
    return 0
  fi
  ensure_parent "${target%/*}"
  current_before=""
  [[ -f "$target" ]] && current_before="$(cat "$target")"
  # --update re-checks ownership and content just before the write.
  write_file_atomic "$target" "$content" "$marker" "" "$current_before" file
  printf '  updated   %s (%s)\n' "$target" "$label"
}

# True if stdin's begin/end marker lines are absent or properly nested pairs.
block_markers_balanced() {
  awk -v b="$1" -v e="$2" '
    $0 == b { if (open) bad = 1; open = 1; next }
    $0 == e { if (!open) bad = 1; open = 0; next }
    END { exit (bad || open) ? 1 : 0 }
  '
}

# Filter stdin, dropping the block (inclusive), plus the separator blank line
# before it and any blank lines left at the start of the file (so reinstalls do
# not accumulate or shuffle blank lines). Blank lines are held back one step and
# only flushed once the next line turns out not to be the begin marker.
strip_block() {
  awk -v b="$1" -v e="$2" '
    $0 == b { skip = 1; pending = 0; next }
    $0 == e { skip = 0; next }
    skip { next }
    $0 == "" { if (pending && printed) print ""; pending = 1; next }
    { if (pending && printed) print ""; pending = 0; print; printed = 1 }
  '
}

# Replace a managed block in place, preserving its position among other
# blocks. Duplicate copies are collapsed to the first occurrence.
replace_managed_block() {
  local begin="$1" end="$2" body="$3"
  AGENTS_MANAGED_BLOCK_BODY="$body" awk -v b="$begin" -v e="$end" '
    function print_body(    count, lines, i) {
      count = split(ENVIRON["AGENTS_MANAGED_BLOCK_BODY"], lines, "\n")
      for (i = 1; i <= count; i++) print lines[i]
    }
    $0 == b {
      if (!seen) {
        seen = 1
        in_block = 1
        print
        print_body()
      } else {
        dropping = 1
      }
      next
    }
    $0 == e && (in_block || dropping) {
      if (in_block) print
      in_block = 0
      dropping = 0
      next
    }
    in_block || dropping { next }
    { print }
  '
}

warn_unbalanced_markers() {
  ((CHECK_MODE)) && return 0
  printf '  WARN      unbalanced marker lines in %s, leaving it untouched (%s)\n' \
    "$1" "$2" >&2
}

# Write `body` as the block between `begin` and `end` in `file`, appended after
# the file's other content. A missing file counts as empty. An unchanged
# result is reported as ok and not written. An empty body is a caller error:
# to drop the block, call managed_block_remove.
managed_block_set() {
  local file="$1" begin="$2" end="$3" body="$4" what="$5"
  if [[ -z "$body" ]]; then
    echo "managed_block_set: empty body for $what in $file" >&2
    return 1
  fi
  local before="" after begin_count kind
  kind="$(check_kind_for_what "$what")"
  if ((CHECK_MODE)) && [[ -L "$file" ]]; then
    check_record "$CHECK_CURRENT_TARGET" "$kind" "$file" foreign
    return 0
  fi
  [[ -f "$file" ]] && before="$(cat "$file")"
  if ! block_markers_balanced "$begin" "$end" <<<"$before"; then
    check_record "$CHECK_CURRENT_TARGET" "$kind" "$file" foreign
    warn_unbalanced_markers "$file" "$what"
    return 0
  fi
  local block="$begin"$'\n'"$body"$'\n'"$end"
  begin_count="$(grep -Fxc "$begin" <<<"$before" || true)"
  if ((CHECK_MODE)); then
    if ((begin_count > 1)); then
      check_record "$CHECK_CURRENT_TARGET" "$kind" "$file" duplicate
    elif ((begin_count == 0)); then
      check_record "$CHECK_CURRENT_TARGET" "$kind" "$file" missing
    elif [[ "$before" != *"$block"* ]]; then
      check_record "$CHECK_CURRENT_TARGET" "$kind" "$file" stale
    fi
    return 0
  fi
  if [[ "$begin_count" -eq 1 && "$before" == *"$block"* ]]; then
    printf '  ok        %s (%s)\n' "$file" "$what"
    return 0
  elif [[ "$begin_count" -gt 0 ]]; then
    after="$(replace_managed_block "$begin" "$end" "$body" <<<"$before")"
  else
    after="$before"
    if [[ -n "$after" ]]; then
      after="$after"$'\n\n'"$block"
    else
      after="$block"
    fi
  fi
  if [[ "$after" == "$before" ]]; then
    printf '  ok        %s (%s)\n' "$file" "$what"
    return 0
  fi
  if ((DRY_RUN)); then
    printf '[dry-run] write %s\n' "$file"
    return 0
  fi
  ensure_parent "${file%/*}"
  # --update re-checks the file just before the write (see write_file_atomic).
  write_file_atomic "$file" "$after" "$begin" "$end" "$before" "$begin_count"
  printf '  updated   %s (%s)\n' "$file" "$what"
}

# Drop the block between `begin` and `end` from `file`, keeping everything
# else. A missing file or an absent block is a silent no-op.
managed_block_remove() {
  local file="$1" begin="$2" end="$3" what="$4"
  [[ -f "$file" ]] || return 0
  local before after
  if ((CHECK_MODE)) && [[ -L "$file" ]]; then
    check_record "$CHECK_CURRENT_TARGET" "$(check_kind_for_what "$what")" "$file" foreign
    return 0
  fi
  before="$(cat "$file")"
  if ! block_markers_balanced "$begin" "$end" <<<"$before"; then
    check_record "$CHECK_CURRENT_TARGET" "$(check_kind_for_what "$what")" "$file" foreign
    warn_unbalanced_markers "$file" "$what"
    return 0
  fi
  if ((CHECK_MODE)); then
    if grep -Fq "$begin" <<<"$before"; then
      local marker_count
      marker_count="$(grep -Fxc "$begin" <<<"$before" || true)"
      if ((marker_count > 1)); then
        check_record "$CHECK_CURRENT_TARGET" "$(check_kind_for_what "$what")" "$file" duplicate
      else
        check_record "$CHECK_CURRENT_TARGET" "$(check_kind_for_what "$what")" "$file" stale
      fi
    fi
    return 0
  fi
  after="$(strip_block "$begin" "$end" <<<"$before")"
  [[ "$after" != "$before" ]] || return 0
  if ((DRY_RUN)); then
    printf '[dry-run] remove %s\n' "$file"
    return 0
  fi
  local marker_count
  marker_count="$(grep -Fxc "$begin" <<<"$before" || true)"
  write_file_atomic "$file" "$after" "$begin" "$end" "$before" "$marker_count"
  printf '  removed   %s from %s\n' "$what" "$file"
}
