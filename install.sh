#!/usr/bin/env bash
# Write this repo's agent configuration into the conventional locations for
# popular coding agents. Skills are never linked: each agent receives them
# through its own channel (Claude and Codex via the plugin marketplace,
# opencode via a skill path in its config; see docs/install.md). What the
# installer writes is exactly what no plugin format can carry:
#   - the managed instruction block composed from instructions/*.md, into
#     ~/.claude/CLAUDE.md and ~/.codex/AGENTS.md (opencode reads the former);
#   - for codex, the [[skills.config]] block in ~/.codex/config.toml that hides
#     routed member skills, and the subagent TOMLs in ~/.codex/agents/.
# Idempotent; reversible via --uninstall.
#
# Usage:
#   ./install.sh --target=claude              # ~/.claude/CLAUDE.md
#   ./install.sh --target=codex               # ~/.codex/AGENTS.md, config.toml, agents/
#   ./install.sh --target=opencode            # legacy cleanup only (see below)
#   ./install.sh --target=all                 # all of the above
#   ./install.sh --target=all --dry-run       # show what would happen
#   ./install.sh --target=all --uninstall     # strip everything this script wrote
#   ./install.sh --target=codex --category=architecture,ai-ml
#
# --category=<name>[,<name>...] (default all) selects which plugins' codex
# extras are written: their subagents and their routed-member suppression. It
# has no subject on the other targets, so it is rejected unless --target
# includes codex.
#
# Migration: earlier versions symlinked skills into every agent's skill and
# command directory. Both install and --uninstall remove those links (any
# symlink under those directories that points into this clone's skills/);
# symlinks pointing elsewhere are never touched.
#
# Exit codes: 0 ok, 2 bad arguments.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

DRY_RUN=0
UNINSTALL=0
TARGET=""
CATEGORY="all"

# Must match the category list in scripts/build_manifest.py.
CATEGORIES="architecture refactoring ai-ml workflow communication personal"

# Print the header comment block: from line 2 up to the first line that is not
# a comment, minus that line. A hardcoded end line silently truncates as the
# block grows — this one cannot drift.
usage() { sed -n '2,/^[^#]/p' "$0" | sed '$d'; }

for arg in "$@"; do
  case "$arg" in
    --target=*)   TARGET="${arg#--target=}" ;;
    --category=*) CATEGORY="${arg#--category=}" ;;
    --dry-run)    DRY_RUN=1 ;;
    --uninstall)  UNINSTALL=1 ;;
    -h|--help)    usage; exit 0 ;;
    --instructions)
      echo "--instructions was removed: composing instructions/ is now what install.sh does by default" >&2
      exit 2 ;;
    --env=*)
      echo "--env was removed: install.sh no longer links skills, so there is nothing to filter" >&2
      exit 2 ;;
    *)            echo "unknown arg: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

case "$TARGET" in
  claude|codex|opencode|all) ;;
  "")
    echo "missing --target=claude|codex|opencode|all" >&2
    usage >&2
    exit 2 ;;
  *)
    echo "invalid --target=$TARGET (expected claude|codex|opencode|all)" >&2
    exit 2 ;;
esac

if [[ "$CATEGORY" != "all" ]]; then
  IFS=',' read -ra _cats <<< "$CATEGORY"
  for c in "${_cats[@]}"; do
    c="${c//[[:space:]]/}"
    [[ -n "$c" ]] || continue
    if [[ " $CATEGORIES " != *" $c "* ]]; then
      echo "invalid --category=$c (expected one of: ${CATEGORIES// /|}|all)" >&2
      usage >&2
      exit 2
    fi
  done
  if [[ "$TARGET" != "codex" && "$TARGET" != "all" ]]; then
    echo "--category selects the codex extras only; it does nothing for --target=$TARGET" >&2
    exit 2
  fi
fi

resolve_targets() {
  if [[ "$TARGET" == "all" ]]; then
    printf 'claude\ncodex\nopencode\n'
  else
    printf '%s\n' "$TARGET"
  fi
}

run() {
  if (( DRY_RUN )); then
    printf '[dry-run] %s\n' "$*"
  else
    "$@"
  fi
}

ensure_parent() {
  local dir="$1"
  if [[ ! -d "$dir" ]]; then
    run mkdir -p "$dir"
  fi
}

# Replace a text file with the given content, atomically. A plain `> "$path"`
# truncates before writing, so an interrupt in between leaves a file we do not
# own in pieces; a temp file plus mv either lands whole or not at all.
write_text_file() {
  local path="$1" content="$2"
  local tmp="$path.tmp.$$"
  if [[ -n "$content" ]]; then
    printf '%s\n' "$content" > "$tmp"
  else
    : > "$tmp"
  fi
  mv "$tmp" "$path"
}

# --- Skill frontmatter readers ----------------------------------------------
#
# Only what the codex extras still need: which skills are routed members of a
# selected category. Read in bash so nothing here depends on python3.

# Read the `activation:` frontmatter value of a SKILL.md. Prints `command`
# for user-invoked skills, `router` for a per-category router skill, `auto`
# otherwise (the default when absent).
skill_activation() {
  local skill_md="$1" line act
  line="$(grep -m1 '^activation:' "$skill_md" 2>/dev/null || true)"
  act="${line#activation:}"
  act="${act//[[:space:]]/}"
  case "$act" in
    command) printf 'command' ;;
    router)  printf 'router' ;;
    *)       printf 'auto' ;;
  esac
}

# Print the `category:` frontmatter value of a SKILL.md (empty if absent).
skill_category() {
  local skill_md="$1" line cat
  line="$(grep -m1 '^category:' "$skill_md" 2>/dev/null || true)"
  cat="${line#category:}"
  printf '%s' "${cat//[[:space:]]/}"
}

# Space-padded list of categories that ship a router skill (activation:
# router). A routed category's auto skills are nested under the router's
# members/ dir and load lazily when the router routes to them.
routed_categories() {
  local out=" "
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    if [[ "$(skill_activation "$d/SKILL.md")" == "router" ]]; then
      out+="$(skill_category "$d/SKILL.md") "
    fi
  done
  printf '%s' "$out"
}

# True if a skill's `category:` frontmatter matches the requested filter.
# `all` matches everything; a skill without the field only matches `all`.
skill_matches_category() {
  local skill_md="$1" want="$2" cat
  [[ "$want" == "all" ]] && return 0
  cat="$(skill_category "$skill_md")"
  [[ -n "$cat" ]] || return 1
  [[ ",${want// /}," == *",$cat,"* ]]
}

# Names of the auto skills nested under a router of a selected category, one
# per line. Codex registers them anyway (see the override section), so these
# are the ones to disable by name.
codex_routed_members() {
  local routed d name
  routed="$(routed_categories)"
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    name="$(basename "$d")"
    skill_matches_category "$d/SKILL.md" "$CATEGORY" || continue
    [[ "$(skill_activation "$d/SKILL.md")" == "auto" ]] || continue
    [[ "$routed" == *" $(skill_category "$d/SKILL.md") "* ]] || continue
    printf '%s\n' "$name"
  done
}

# --- Legacy skill symlink migration -----------------------------------------
#
# Earlier versions of this script symlinked skills (and, for command skills,
# their SKILL.md) into each agent's skill and command directories. Skills now
# reach every agent through a channel of its own, and a symlink left behind
# registers each skill a second time. So both install and uninstall remove
# every symlink under those directories that points into this clone's skills/,
# whether it still resolves or not. A symlink pointing anywhere else — another
# clone, a foreign skill — is never touched, and neither is a real directory.

legacy_skill_dirs_for() {
  case "$1" in
    claude)
      printf '%s/.claude/skills\n%s/.claude/commands\n' "$HOME" "$HOME" ;;
    codex)
      # ~/.codex/prompts held command skills before Codex deprecated prompts.
      printf '%s/.codex/skills\n%s/.codex/prompts\n' "$HOME" "$HOME" ;;
    opencode)
      # ~/.config/opencode/agent was a mistaken early location for skills.
      printf '%s/.config/opencode/skills\n%s/.config/opencode/command\n%s/.config/opencode/agent\n' \
        "$HOME" "$HOME" "$HOME" ;;
    *) echo "unknown target: $1" >&2; return 1 ;;
  esac
}

remove_legacy_skill_links() {
  local target="$1" dir entry link_target
  while IFS= read -r dir; do
    [[ -n "$dir" && -d "$dir" ]] || continue
    for entry in "$dir"/*; do
      [[ -L "$entry" ]] || continue
      link_target="$(readlink "$entry")"
      [[ "$link_target" == "$REPO_ROOT/skills/"* ]] || continue
      run rm "$entry"
      printf '  removed   %s (skills are no longer symlinked)\n' "$entry"
    done
  done < <(legacy_skill_dirs_for "$target")
}

# --- Legacy Codex MCP cleanup ----------------------------------------------
#
# Earlier versions registered each plugin's knowledge-base MCP server in
# ~/.codex/config.toml between marker comments, backed by a runtime venv at a
# fixed path. Those servers are gone — the skills' references/ pages are read
# directly now — so both install and uninstall strip whatever a previous
# version left behind. Install has to do it too: an upgrade would otherwise
# keep Codex pointing at a server script this repo no longer ships.

codex_config_path() { printf '%s/.codex/config.toml' "$HOME"; }

# Replace ~/.codex/config.toml with the given content, atomically (see
# write_text_file).
write_codex_config() { write_text_file "$1" "$2"; }

# Categories that ever shipped an .mcp.json. Hardcoded, because the files this
# list was once derived from no longer exist.
LEGACY_MCP_CATEGORIES="architecture refactoring"

codex_mcp_runtime_dir() { printf '%s/.codex/agents-mcp-runtime' "$HOME"; }

mcp_begin_marker() {
  printf '# >>> agents:%s MCP servers (managed by install.sh, do not edit) >>>' "$1"
}

mcp_end_marker() {
  printf '# <<< agents:%s MCP servers <<<' "$1"
}

# True if stdin's marker lines for a category are absent or form properly
# nested begin/end pairs. A hand-edited config with a dangling begin or end
# marker must not be stripped: strip_mcp_block would silently drop
# everything from the begin marker to end of file.
mcp_markers_balanced() {
  awk -v b="$(mcp_begin_marker "$1")" -v e="$(mcp_end_marker "$1")" '
    $0 == b { if (open) bad = 1; open = 1; next }
    $0 == e { if (!open) bad = 1; open = 0; next }
    END { exit (bad || open) ? 1 : 0 }
  '
}

# Filter stdin, dropping the marker block (inclusive) for a category, plus
# the separator blank line before it and any blank lines left at the start
# of the file (so reinstalls do not accumulate or shuffle blank lines).
# Blank lines are held back one step and only flushed once the next line
# turns out not to be our begin marker.
strip_mcp_block() {
  awk -v b="$(mcp_begin_marker "$1")" -v e="$(mcp_end_marker "$1")" '
    $0 == b { skip = 1; pending = 0; next }
    $0 == e { skip = 0; next }
    skip { next }
    $0 == "" { if (pending && printed) print ""; pending = 1; next }
    { if (pending && printed) print ""; pending = 0; print; printed = 1 }
  '
}

# Drop every managed MCP block a previous version wrote, plus the runtime venv
# it provisioned. Foreign [mcp_servers.*] tables live outside our markers and
# are never touched; a hand-edited unbalanced marker pair leaves the file alone.
remove_legacy_codex_mcp() {
  local config; config="$(codex_config_path)"
  local cat before after
  if [[ -f "$config" ]]; then
    for cat in $LEGACY_MCP_CATEGORIES; do
      before="$(cat "$config")"
      if ! mcp_markers_balanced "$cat" <<< "$before"; then
        printf '  WARN      unbalanced %s marker lines in %s (leaving it untouched)\n' \
          "$cat" "$config" >&2
        continue
      fi
      after="$(strip_mcp_block "$cat" <<< "$before")"
      [[ "$after" != "$before" ]] || continue
      if (( DRY_RUN )); then
        printf '[dry-run] remove legacy %s MCP servers from %s\n' "$cat" "$config"
        continue
      fi
      write_codex_config "$config" "$after"
      printf '  removed   legacy %s MCP servers from %s\n' "$cat" "$config"
    done
  fi

  local venv; venv="$(codex_mcp_runtime_dir)"
  if [[ -d "$venv" ]]; then
    if (( DRY_RUN )); then
      printf '[dry-run] remove legacy MCP runtime venv %s\n' "$venv"
    else
      rm -rf "$venv"
      printf '  removed   legacy MCP runtime venv %s\n' "$venv"
    fi
  fi
}

# --- Codex routed-member skill overrides -----------------------------------
#
# Codex discovers skills by scanning its skill roots recursively and following
# symlinks (openai/codex#22275), so the sub-skills nested under a router's
# members/ dir get registered as independent skills — defeating the router's
# progressive disclosure. (Claude registers only top-level skills, so it is
# unaffected.) The marketplace plugin carries the same nested members, so this
# applies whichever way the skills arrive. To keep the members hidden under
# codex, disable each nested member by name in ~/.codex/config.toml via a
# [[skills.config]] entry (enabled = false), which drops it from the model's
# skill list. The block is marker-delimited so install and uninstall stay
# idempotent and never touch config we do not own.

skill_override_begin_marker() {
  printf '# >>> agents routed-member skill overrides (managed by install.sh, do not edit) >>>'
}

skill_override_end_marker() {
  printf '# <<< agents routed-member skill overrides <<<'
}

# True if stdin's override marker lines are absent or form a properly nested
# begin/end pair (see mcp_markers_balanced for the rationale).
skill_override_markers_balanced() {
  awk -v b="$(skill_override_begin_marker)" -v e="$(skill_override_end_marker)" '
    $0 == b { if (open) bad = 1; open = 1; next }
    $0 == e { if (!open) bad = 1; open = 0; next }
    END { exit (bad || open) ? 1 : 0 }
  '
}

# Filter stdin, dropping the override marker block (inclusive) and normalising
# surrounding blank lines (see strip_mcp_block).
strip_skill_override_block() {
  awk -v b="$(skill_override_begin_marker)" -v e="$(skill_override_end_marker)" '
    $0 == b { skip = 1; pending = 0; next }
    $0 == e { skip = 0; next }
    skip { next }
    $0 == "" { if (pending && printed) print ""; pending = 1; next }
    { if (pending && printed) print ""; pending = 0; print; printed = 1 }
  '
}

# Render one [[skills.config]] disable table per member name read on stdin.
render_skill_override_toml() {
  local name first=1
  while IFS= read -r name; do
    [[ -n "$name" ]] || continue
    if [[ ! "$name" =~ ^[A-Za-z0-9_-]+$ ]]; then
      printf '  WARN      skill name %q is not a bare identifier (skipping override)\n' \
        "$name" >&2
      continue
    fi
    (( first )) || printf '\n'
    first=0
    printf '[[skills.config]]\nname = "%s"\nenabled = false\n' "$name"
  done
}

# Strip our override block from ~/.codex/config.toml (leaving foreign config).
remove_codex_member_overrides() {
  local config; config="$(codex_config_path)"
  [[ -f "$config" ]] || return 0
  local before after
  before="$(cat "$config")"
  if ! skill_override_markers_balanced <<< "$before"; then
    printf '  WARN      unbalanced skill-override marker lines in %s (leaving it untouched)\n' \
      "$config" >&2
    return 0
  fi
  after="$(strip_skill_override_block <<< "$before")"
  [[ "$after" != "$before" ]] || return 0
  if (( DRY_RUN )); then
    printf '[dry-run] remove routed-member skill overrides from %s\n' "$config"
    return 0
  fi
  write_codex_config "$config" "$after"
  printf '  removed   routed-member skill overrides from %s\n' "$config"
}

# Write the managed override block that disables the nested router members
# named on stdin (one per line). With no names, any stale block is removed.
# Uses only shell built-ins and the same core tools as the rest of install.sh
# (no sort/wc/tr) so it works under the minimal sandboxed PATH.
install_codex_member_overrides() {
  local config; config="$(codex_config_path)"
  local members="" count=0 name
  while IFS= read -r name; do
    [[ -n "${name//[[:space:]]/}" ]] || continue
    members+="$name"$'\n'
    count=$((count + 1))
  done
  if [[ -z "$members" ]]; then
    remove_codex_member_overrides
    return 0
  fi
  if (( DRY_RUN )); then
    remove_codex_member_overrides
    printf '[dry-run] disable %s routed member skills in %s\n' "$count" "$config"
    return 0
  fi
  mkdir -p "$(dirname "$config")"
  [[ -f "$config" ]] || : > "$config"
  if ! skill_override_markers_balanced < "$config"; then
    printf '  WARN      unbalanced skill-override marker lines in %s (leaving it untouched)\n' \
      "$config" >&2
    return 0
  fi
  local rest toml
  rest="$(strip_skill_override_block < "$config")"
  toml="$(printf '%s' "$members" | render_skill_override_toml)"
  {
    if [[ -n "$rest" ]]; then printf '%s\n\n' "$rest"; fi
    skill_override_begin_marker; printf '\n'
    printf '%s\n' "$toml"
    skill_override_end_marker; printf '\n'
  } > "$config.tmp.$$"
  mv "$config.tmp.$$" "$config"
  printf '  skills    %s routed members disabled in %s\n' "$count" "$config"
}

# --- Codex custom agent registration ----------------------------------------
#
# Claude loads plugins/<category>/agents/*.md natively; Codex CLI discovers
# custom agents as TOML files under ~/.codex/agents/ instead, and its plugin
# format has no subagent component, so the marketplace never delivers them.
# Each agent's frontmatter name/description and Markdown body (its system
# prompt) are converted to a generated <name>.toml carrying a marker comment,
# so install and uninstall never touch files we did not generate. The `tools:`
# and `model:` frontmatter fields have no Codex equivalent and are dropped
# (model and sandbox are inherited from the parent session).

codex_agents_dir() { printf '%s/.codex/agents' "$HOME"; }

AGENT_MARKER='# generated by fabiandistler/agents install.sh; do not edit'

# Categories selected by --category that ship subagents.
agent_categories() {
  local c
  if [[ "$CATEGORY" == "all" ]]; then
    for c in $CATEGORIES; do
      if compgen -G "$REPO_ROOT/plugins/$c/agents/*.md" >/dev/null; then
        printf '%s\n' "$c"
      fi
    done
  else
    local IFS=','
    for c in $CATEGORY; do
      c="${c//[[:space:]]/}"
      if [[ -n "$c" ]] && compgen -G "$REPO_ROOT/plugins/$c/agents/*.md" >/dev/null; then
        printf '%s\n' "$c"
      fi
    done
  fi
  return 0
}

# Render one agents/<name>.md as a Codex custom-agent TOML file, with
# ${CLAUDE_PLUGIN_ROOT} resolved to the plugin directory in this repo.
plugin_agent_toml() {
  local md="$1" plugin_dir="$2" marker="$3"
  python3 - "$md" "$plugin_dir" "$marker" <<'PY'
import json
import sys
from pathlib import Path

try:
    md_path, plugin_dir, marker = sys.argv[1], sys.argv[2], sys.argv[3]
    lines = Path(md_path).read_text(encoding="utf-8").splitlines()
    if lines[0].strip() != "---":
        raise ValueError("missing frontmatter")
    close = lines[1:].index("---") + 1
    body = "\n".join(lines[close + 1 :]).strip()
    if not body:
        raise ValueError("empty agent body")

    # Minimal YAML subset: `key: value` plus `key: >-` folded blocks whose
    # continuation lines are indented; folded newlines become spaces.
    fm: dict[str, str] = {}
    key = None
    parts: list[str] = []

    def flush():
        if key is not None:
            fm[key] = " ".join(p.strip() for p in parts if p.strip())

    for line in lines[1:close]:
        if line[:1] in (" ", "\t") and key is not None:
            parts.append(line)
            continue
        flush()
        k, _, v = line.partition(":")
        key, parts = k.strip(), [v.replace(">-", "", 1) if v.strip() == ">-" else v]
    flush()

    name, desc = fm["name"], fm["description"]
    body = body.replace("${CLAUDE_PLUGIN_ROOT}", plugin_dir) + "\n"
    body = body.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')

    print(marker)
    print(f"name = {json.dumps(name)}")
    print(f"description = {json.dumps(desc)}")
    print()
    print(f'developer_instructions = """\n{body}"""')
except Exception:
    sys.exit(1)
PY
}

install_codex_agents() {
  local agents_dir; agents_dir="$(codex_agents_dir)"
  local cats; cats="$(agent_categories)"
  [[ -n "$cats" ]] || return 0
  if ! command -v python3 >/dev/null 2>&1; then
    printf '  WARN      python3 not found; cannot install agents in %s\n' \
      "$agents_dir" >&2
    return 0
  fi
  local cat md name dest toml
  while IFS= read -r cat; do
    [[ -n "$cat" ]] || continue
    for md in "$REPO_ROOT/plugins/$cat/agents/"*.md; do
      name="$(basename "$md" .md)"
      dest="$agents_dir/$name.toml"
      if ! toml="$(plugin_agent_toml "$md" "$REPO_ROOT/plugins/$cat" "$AGENT_MARKER")"; then
        printf '  WARN      failed to convert %s (skipping)\n' "$md" >&2
        continue
      fi
      if (( DRY_RUN )); then
        printf '[dry-run] write agent %s\n' "$dest"
        continue
      fi
      if [[ -e "$dest" ]] && ! grep -qF "$AGENT_MARKER" "$dest"; then
        printf '  WARN      %s exists and was not generated by us (skipping)\n' \
          "$dest" >&2
        continue
      fi
      mkdir -p "$agents_dir"
      printf '%s\n' "$toml" > "$dest.tmp.$$"
      mv "$dest.tmp.$$" "$dest"
      printf '  agent     %s -> %s\n' "$name" "$dest"
    done
  done <<< "$cats"
}

uninstall_codex_agents() {
  local agents_dir; agents_dir="$(codex_agents_dir)"
  local cat md name dest
  while IFS= read -r cat; do
    [[ -n "$cat" ]] || continue
    for md in "$REPO_ROOT/plugins/$cat/agents/"*.md; do
      name="$(basename "$md" .md)"
      dest="$agents_dir/$name.toml"
      [[ -f "$dest" ]] || continue
      if ! grep -qF "$AGENT_MARKER" "$dest"; then
        printf '  WARN      %s was not generated by us (skipping)\n' "$dest" >&2
        continue
      fi
      if (( DRY_RUN )); then
        printf '[dry-run] remove agent %s\n' "$dest"
        continue
      fi
      rm "$dest"
      printf '  removed   %s\n' "$dest"
    done
  done < <(agent_categories)
}

# --- Agent instruction files ------------------------------------------------
#
# instructions/*.md are single-topic rule fragments composed into one managed
# block inside each agent's global instruction file, so a rule is authored once
# instead of being copied by hand into every agent's config (which is how
# ~/.claude/CLAUDE.md and ~/.codex/AGENTS.md drifted apart in the first place).
# Ordering is the numeric filename prefix: glob order is already deterministic,
# so this needs no sort. No plugin format delivers standing instructions, which
# is why this stays an installer job — and the installer's default one.
#
# The block is marker-delimited like the Codex config blocks above, so whatever
# the user keeps outside it — an @-import, a machine-specific note — survives
# install, reinstall and uninstall untouched.
#
# opencode has no destination on purpose. Its instruction loader reads
# <config>/AGENTS.md *and* ~/.claude/CLAUDE.md unless disableClaudeCodePrompt
# is set, so giving it its own copy would load every rule twice per session.
# Note the filenames differ per agent (CLAUDE.md vs AGENTS.md): the content is
# one AGENTS.md-style document, written to whatever each agent actually reads.

instructions_dir() { printf '%s/instructions' "$REPO_ROOT"; }

# Global instruction file for a target, or empty when the target deliberately
# has none (see above). Unknown targets are an error.
instruction_file_for() {
  case "$1" in
    claude)   printf '%s/.claude/CLAUDE.md' "$HOME" ;;
    codex)    printf '%s/.codex/AGENTS.md'  "$HOME" ;;
    opencode) ;;
    *) echo "unknown target: $1" >&2; return 1 ;;
  esac
}

# Read a frontmatter field from a fragment. Prints the raw value, empty when
# the field is absent.
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

# Fragment paths for a target, in filename order.
list_instruction_fragments() {
  local want="$1" file
  for file in "$(instructions_dir)"/*.md; do
    [[ -f "$file" ]] || continue
    fragment_matches_target "$file" "$want" || continue
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
  local file first=1
  while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    (( first )) || printf '\n'
    first=0
    fragment_body "$file"
  done
}

instructions_begin_marker() {
  printf '<!-- >>> agents instructions (managed by install.sh, do not edit) >>> -->'
}

instructions_end_marker() {
  printf '<!-- <<< agents instructions <<< -->'
}

# True if stdin's marker lines are absent or form a properly nested begin/end
# pair (see mcp_markers_balanced for the rationale).
instructions_markers_balanced() {
  awk -v b="$(instructions_begin_marker)" -v e="$(instructions_end_marker)" '
    $0 == b { if (open) bad = 1; open = 1; next }
    $0 == e { if (!open) bad = 1; open = 0; next }
    END { exit (bad || open) ? 1 : 0 }
  '
}

# Filter stdin, dropping the instructions block (inclusive) and normalising
# surrounding blank lines (see strip_mcp_block).
strip_instructions_block() {
  awk -v b="$(instructions_begin_marker)" -v e="$(instructions_end_marker)" '
    $0 == b { skip = 1; pending = 0; next }
    $0 == e { skip = 0; next }
    skip { next }
    $0 == "" { if (pending && printed) print ""; pending = 1; next }
    { if (pending && printed) print ""; pending = 0; print; printed = 1 }
  '
}

# Compose the fragments for a target and write them into its instruction file
# as the managed block, replacing whatever the block held before. Content
# outside the markers is preserved; unbalanced markers leave the file alone.
install_instructions() {
  local target="$1" dest
  dest="$(instruction_file_for "$target")" || return 1
  if [[ -z "$dest" ]]; then
    printf '  note      instructions: %s reads them from %s/.claude/CLAUDE.md (nothing to write)\n' \
      "$target" "$HOME"
    return 0
  fi
  local fragments count=0 file
  fragments="$(list_instruction_fragments "$target")"
  while IFS= read -r file; do
    if [[ -n "$file" ]]; then
      count=$((count + 1))
    fi
  done <<< "$fragments"
  if (( count == 0 )); then
    printf '  WARN      no instruction fragments match target %s (skipping %s)\n' \
      "$target" "$dest" >&2
    return 0
  fi
  local body; body="$(render_instructions <<< "$fragments")"
  local before="" after block
  [[ -f "$dest" ]] && before="$(cat "$dest")"
  if ! instructions_markers_balanced <<< "$before"; then
    printf '  WARN      unbalanced instruction marker lines in %s (leaving it untouched)\n' \
      "$dest" >&2
    return 0
  fi
  after="$(strip_instructions_block <<< "$before")"
  block="$(instructions_begin_marker)"$'\n'"$body"$'\n'"$(instructions_end_marker)"
  if [[ -n "$after" ]]; then
    after="$after"$'\n\n'"$block"
  else
    after="$block"
  fi
  if [[ "$after" == "$before" ]]; then
    printf '  ok        %s (%s instruction fragments)\n' "$dest" "$count"
    return 0
  fi
  if (( DRY_RUN )); then
    printf '[dry-run] write %s instruction fragments into %s\n' "$count" "$dest"
    return 0
  fi
  ensure_parent "${dest%/*}"
  write_text_file "$dest" "$after"
  printf '  updated   %s (%s instruction fragments)\n' "$dest" "$count"
}

# Strip our instructions block from a target's file, leaving the rest.
remove_instructions() {
  local target="$1" dest
  dest="$(instruction_file_for "$target")" || return 1
  [[ -n "$dest" && -f "$dest" ]] || return 0
  local before after
  before="$(cat "$dest")"
  if ! instructions_markers_balanced <<< "$before"; then
    printf '  WARN      unbalanced instruction marker lines in %s (leaving it untouched)\n' \
      "$dest" >&2
    return 0
  fi
  after="$(strip_instructions_block <<< "$before")"
  [[ "$after" != "$before" ]] || return 0
  if (( DRY_RUN )); then
    printf '[dry-run] remove instructions block from %s\n' "$dest"
    return 0
  fi
  write_text_file "$dest" "$after"
  printf '  removed   instructions block from %s\n' "$dest"
}

main() {
  [[ "$CATEGORY" != "all" ]] && printf 'category filter: %s\n' "$CATEGORY"

  while IFS= read -r target; do
    [[ -z "$target" ]] && continue
    printf '%s:\n' "$target"
    # Runs on both paths: an upgrade must drop the links a version that still
    # symlinked skills left behind, or every skill registers twice.
    remove_legacy_skill_links "$target"
    if [[ "$target" == "codex" ]]; then
      # Likewise for the managed block a version that still registered the
      # knowledge-base MCP servers wrote.
      remove_legacy_codex_mcp
      if (( UNINSTALL )); then
        uninstall_codex_agents
        remove_codex_member_overrides
      else
        install_codex_agents
        codex_routed_members | install_codex_member_overrides
      fi
    fi
    if (( UNINSTALL )); then
      remove_instructions "$target"
    else
      install_instructions "$target"
    fi
  done < <(resolve_targets)
}

main
