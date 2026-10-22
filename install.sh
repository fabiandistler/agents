#!/usr/bin/env bash
# Symlink the skills in this repo into the conventional install paths
# for popular coding agents. Idempotent; reversible via --uninstall.
#
# Usage:
#   ./install.sh --target=claude              # ~/.claude/skills/<skill>
#   ./install.sh --target=codex               # ~/.codex/skills/<skill>
#   ./install.sh --target=opencode            # ~/.config/opencode/skills/<skill>
#   ./install.sh --target=all                 # all of the above
#   ./install.sh --target=all --dry-run       # show what would happen
#   ./install.sh --target=all --uninstall     # remove symlinks owned by us
#   ./install.sh --target=claude --env=chat   # only chat skills
#   ./install.sh --target=codex  --env=coding # only coding skills
#   ./install.sh --target=claude --category=architecture,refactoring
#   ./install.sh --target=all --instructions   # also sync the rule files
#   ./install.sh --target=all --merge-guard    # also block agent PR merges
#
# --env=coding|chat|all (default all) selects which skills to (un)install,
# based on each skill's `environments:` frontmatter field. A skill with no
# such field belongs to every environment.
#
# --category=<name>[,<name>...] (default all) further narrows the selection
# to skills whose `category:` frontmatter field matches one of the given
# categories. Combinable with --env.
#
# A skill may also restrict itself to some agents with a `targets:` frontmatter
# field (comma-separated subset of claude, codex, opencode; absent means all).
# A skill that excludes a target is never linked there, and an existing link we
# own is removed on the next install. Use it when a runtime already ships an
# equivalent of its own.
#
# Skills with `activation: command` in their frontmatter are user-invoked,
# not model-triggered. For claude and opencode they are linked into the
# target's command directory (~/.claude/commands, ~/.config/opencode/command)
# as <name>.md instead of the skills directory, keeping them out of the
# auto-trigger metadata. Codex custom prompts (~/.codex/prompts) are
# deprecated, so under codex these skills install into the skills directory
# like any other; their agents/openai.yaml sidecar
# (policy.allow_implicit_invocation: false) keeps Codex from auto-triggering
# them, so they stay explicit-only. --uninstall reverses this, and codex
# installs also remove any leftover ~/.codex/prompts symlinks we created.
#
# A category may ship a router skill (`activation: router`, named after the
# category). Its auto skills are nested under the router's members/ dir, so
# only the router is linked at top level; the members load lazily when the
# router routes to them, keeping the category to a single trigger entry. The
# nested members are never linked flat; a flat link left by a pre-router
# install is removed, on both the install and the uninstall path.
# Claude registers only top-level skills, so the members stay hidden there.
# Codex, however, discovers skills recursively and follows symlinks
# (openai/codex#22275), so it would register each nested members/<name>/SKILL.md
# as its own skill. To preserve the router's progressive disclosure under codex,
# install additionally disables every nested member by name in
# ~/.codex/config.toml via a managed [[skills.config]] block (enabled = false),
# which drops them from the model's skill list; --uninstall removes the block.
#
# The codex target additionally installs the full plugins, not just the
# skills. Requires python3 (skipped with a warning otherwise); --uninstall
# reverses it. --env only filters skills; the plugin extras follow
# --category:
#   - Each selected plugin's subagents (plugins/<category>/agents/*.md) are
#     converted to Codex custom agents in ~/.codex/agents/<name>.toml.
#
# --instructions (off by default) additionally composes the Markdown
# fragments in instructions/ into each agent's global instruction file
# (~/.claude/CLAUDE.md, ~/.codex/AGENTS.md, ~/.config/opencode/AGENTS.md), as
# one marker-delimited managed block. Fragments are ordered by their numeric filename prefix and may limit
# themselves to some agents with a `targets:` frontmatter field, as skills do.
# For claude, a fragment with a `paths:` field (comma-separated globs) goes to
# ~/.claude/rules/agents-<fragment>.md instead and loads only when Claude reads
# a matching file; codex and opencode keep it in their block.
# Anything outside the markers is left untouched, so hand-written notes and
# @-imports survive; --uninstall strips the block and nothing else. opencode
# gets its own ~/.config/opencode/AGENTS.md: it reads ~/.claude/CLAUDE.md only
# as a fallback when that file is missing, and opencode V2 not at all.
#
# --merge-guard (off by default) installs a model-free pre-tool hook that stops
# the agent from merging pull requests or enabling auto-merge; the human merges.
# The check is scripts/pr_merge_guard.py (needs python3 at hook time). claude:
# a PreToolUse entry in ~/.claude/settings.json; codex: a managed [hooks] block
# in ~/.codex/config.toml (trust it once in Codex's /hooks); opencode: a plugin
# symlink in ~/.config/opencode/plugins/. --merge-guard --uninstall removes
# exactly these, leaving other settings and hooks alone.
#
# Conservative behaviour:
#   - Existing correct symlink:        skip (idempotent).
#   - Symlink pointing elsewhere:      skip with a warning, never overwrite.
#   - Regular file or non-empty dir:   skip with a warning, never overwrite.
#   - Uninstall only removes a symlink whose target is a path inside this
#     repo, so foreign files at that location are never touched.
#   - Both install and uninstall prune dangling symlinks left over from
#     skills this repo no longer ships, again only when the (now missing)
#     target was inside this repo.
#   - Earlier versions registered knowledge-base MCP servers in
#     ~/.codex/config.toml. They are gone; install and uninstall both strip
#     any leftover managed block and its runtime venv. Only our own marker
#     block is touched — a foreign [mcp_servers.<name>] table survives, and
#     hand-edited unbalanced markers leave the whole file alone.
#   - Generated agent files carry a marker comment; a file at the same path
#     without the marker is never overwritten, and uninstall only removes
#     marker-carrying files.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

DRY_RUN=0
UNINSTALL=0
INSTRUCTIONS=0
MERGE_GUARD=0
TARGET=""
ENV="all"
CATEGORY="all"

# Must match the category list in scripts/build_manifest.py.
CATEGORIES="architecture refactoring ai-ml workflow communication personal"

# Print the header comment block: from line 2 up to the first line that is not
# a comment, minus that line. A hardcoded end line silently truncates as the
# block grows — this one cannot drift.
usage() { sed -n '2,/^[^#]/p' "$0" | sed '$d'; }

for arg in "$@"; do
  case "$arg" in
    --target=*) TARGET="${arg#--target=}" ;;
    --env=*) ENV="${arg#--env=}" ;;
    --category=*) CATEGORY="${arg#--category=}" ;;
    --dry-run) DRY_RUN=1 ;;
    --instructions) INSTRUCTIONS=1 ;;
    --merge-guard) MERGE_GUARD=1 ;;
    --uninstall) UNINSTALL=1 ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "unknown arg: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  echo "missing --target=claude|codex|opencode|all" >&2
  usage >&2
  exit 2
fi

case "$ENV" in
  all | coding | chat) ;;
  *)
    echo "invalid --env=$ENV (expected coding|chat|all)" >&2
    usage >&2
    exit 2
    ;;
esac

if [[ "$CATEGORY" != "all" ]]; then
  IFS=',' read -ra _cats <<<"$CATEGORY"
  for c in "${_cats[@]}"; do
    c="${c//[[:space:]]/}"
    [[ -n "$c" ]] || continue
    if [[ " $CATEGORIES " != *" $c "* ]]; then
      echo "invalid --category=$c (expected one of: ${CATEGORIES// /|}|all)" >&2
      usage >&2
      exit 2
    fi
  done
fi

target_dir_for() {
  case "$1" in
    claude) printf '%s/.claude/skills\n' "$HOME" ;;
    codex) printf '%s/.codex/skills\n' "$HOME" ;;
    opencode) printf '%s/.config/opencode/skills\n' "$HOME" ;;
    *)
      echo "unknown target: $1" >&2
      return 1
      ;;
  esac
}

# Where each target discovers user-invoked commands. `activation: command`
# skills go here (as <name>.md) instead of the skills directory.
target_command_dir_for() {
  case "$1" in
    claude) printf '%s/.claude/commands\n' "$HOME" ;;
    opencode) printf '%s/.config/opencode/command\n' "$HOME" ;;
    *)
      echo "unknown target: $1" >&2
      return 1
      ;;
  esac
}

resolve_targets() {
  if [[ "$TARGET" == "all" ]]; then
    printf 'claude\ncodex\nopencode\n'
  else
    printf '%s\n' "$TARGET"
  fi
}

# Read the comma-separated `environments:` frontmatter value of a SKILL.md.
# Prints the raw value (may be empty if the field is absent).
skill_environments() {
  local skill_md="$1" line
  line="$(grep -m1 '^environments:' "$skill_md" 2>/dev/null || true)"
  printf '%s' "${line#environments:}"
}

# True if a skill belongs to the requested environment. A skill with no
# `environments:` field belongs to every environment.
skill_matches_env() {
  local skill_md="$1" want="$2" envs
  [[ "$want" == "all" ]] && return 0
  envs="$(skill_environments "$skill_md")"
  [[ -z "${envs//[[:space:]]/}" ]] && return 0
  local IFS=','
  for e in $envs; do
    e="${e//[[:space:]]/}"
    [[ "$e" == "$want" ]] && return 0
  done
  return 1
}

# Read the comma-separated `targets:` frontmatter value of a SKILL.md.
# Prints the raw value (may be empty if the field is absent).
skill_targets() {
  local skill_md="$1" line
  line="$(grep -m1 '^targets:' "$skill_md" 2>/dev/null || true)"
  printf '%s' "${line#targets:}"
}

# True if a skill should be installed for the given target. A skill with no
# `targets:` field belongs to every target.
skill_matches_target() {
  local skill_md="$1" want="$2" targets
  targets="$(skill_targets "$skill_md")"
  [[ -z "${targets//[[:space:]]/}" ]] && return 0
  local IFS=','
  for t in $targets; do
    t="${t//[[:space:]]/}"
    [[ "$t" == "$want" ]] && return 0
  done
  return 1
}

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
    router) printf 'router' ;;
    *) printf 'auto' ;;
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
# members/ dir, so install.sh links only the router and skips the members.
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
  local skill_md="$1" want="$2" line cat
  [[ "$want" == "all" ]] && return 0
  line="$(grep -m1 '^category:' "$skill_md" 2>/dev/null || true)"
  cat="${line#category:}"
  cat="${cat//[[:space:]]/}"
  [[ -n "$cat" ]] || return 1
  [[ ",${want// /}," == *",$cat,"* ]]
}

list_skills() {
  # A directory under skills/ is a skill iff it contains SKILL.md.
  for d in "$REPO_ROOT"/skills/*/; do
    local name
    name="$(basename "$d")"
    [[ -f "$d/SKILL.md" ]] || continue
    skill_matches_env "$d/SKILL.md" "$ENV" || continue
    skill_matches_category "$d/SKILL.md" "$CATEGORY" || continue
    printf '%s\n' "$name"
  done
}

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
  local path="$1" content="$2"
  local tmp="$path.tmp.$$"
  if [[ -n "$content" ]]; then
    printf '%s\n' "$content" >"$tmp"
  else
    : >"$tmp"
  fi
  mv "$tmp" "$path"
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

warn_unbalanced_markers() {
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
  local before="" after
  [[ -f "$file" ]] && before="$(cat "$file")"
  if ! block_markers_balanced "$begin" "$end" <<<"$before"; then
    warn_unbalanced_markers "$file" "$what"
    return 0
  fi
  after="$(strip_block "$begin" "$end" <<<"$before")"
  local block="$begin"$'\n'"$body"$'\n'"$end"
  if [[ -n "$after" ]]; then
    after="$after"$'\n\n'"$block"
  else
    after="$block"
  fi
  if [[ "$after" == "$before" ]]; then
    printf '  ok        %s (%s)\n' "$file" "$what"
    return 0
  fi
  if ((DRY_RUN)); then
    printf '[dry-run] write %s into %s\n' "$what" "$file"
    return 0
  fi
  ensure_parent "${file%/*}"
  write_file_atomic "$file" "$after"
  printf '  updated   %s (%s)\n' "$file" "$what"
}

# Drop the block between `begin` and `end` from `file`, keeping everything
# else. A missing file or an absent block is a silent no-op.
managed_block_remove() {
  local file="$1" begin="$2" end="$3" what="$4"
  [[ -f "$file" ]] || return 0
  local before after
  before="$(cat "$file")"
  if ! block_markers_balanced "$begin" "$end" <<<"$before"; then
    warn_unbalanced_markers "$file" "$what"
    return 0
  fi
  after="$(strip_block "$begin" "$end" <<<"$before")"
  [[ "$after" != "$before" ]] || return 0
  if ((DRY_RUN)); then
    printf '[dry-run] remove %s from %s\n' "$what" "$file"
    return 0
  fi
  write_file_atomic "$file" "$after"
  printf '  removed   %s from %s\n' "$what" "$file"
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

# Drop every managed MCP block a previous version wrote, plus the runtime venv
# it provisioned. Foreign [mcp_servers.*] tables live outside our markers and
# are never touched.
remove_legacy_codex_mcp() {
  local config cat
  config="$(codex_config_path)"
  for cat in $LEGACY_MCP_CATEGORIES; do
    managed_block_remove "$config" "$(mcp_begin_marker "$cat")" \
      "$(mcp_end_marker "$cat")" "legacy $cat MCP servers"
  done

  local venv
  venv="$(codex_mcp_runtime_dir)"
  if [[ -d "$venv" ]]; then
    if ((DRY_RUN)); then
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
# unaffected.) To keep the members hidden under codex, disable each nested
# member by name in ~/.codex/config.toml via a [[skills.config]] entry
# (enabled = false), which drops it from the model's skill list. The block is
# marker-delimited so install and uninstall stay idempotent and never touch
# config we do not own.

skill_override_begin_marker() {
  printf '# >>> agents routed-member skill overrides (managed by install.sh, do not edit) >>>'
}

skill_override_end_marker() {
  printf '# <<< agents routed-member skill overrides <<<'
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
    ((first)) || printf '\n'
    first=0
    printf '[[skills.config]]\nname = "%s"\nenabled = false\n' "$name"
  done
}

# Strip our override block from ~/.codex/config.toml (leaving foreign config).
remove_codex_member_overrides() {
  managed_block_remove "$(codex_config_path)" "$(skill_override_begin_marker)" \
    "$(skill_override_end_marker)" "routed-member skill overrides"
}

# Write the managed override block that disables the nested router members
# named on stdin (one per line). With no names, any stale block is removed.
# Uses only shell built-ins and the same core tools as the rest of install.sh
# (no sort/wc/tr) so it works under the minimal sandboxed PATH.
install_codex_member_overrides() {
  local members="" count=0 name toml
  while IFS= read -r name; do
    [[ -n "${name//[[:space:]]/}" ]] || continue
    members+="$name"$'\n'
    count=$((count + 1))
  done
  toml="$(printf '%s' "$members" | render_skill_override_toml)"
  if [[ -z "$toml" ]]; then
    remove_codex_member_overrides
    return 0
  fi
  managed_block_set "$(codex_config_path)" "$(skill_override_begin_marker)" \
    "$(skill_override_end_marker)" "$toml" "$count routed members disabled"
}

# --- Codex custom agent registration ----------------------------------------
#
# Claude loads plugins/<category>/agents/*.md natively; Codex CLI discovers
# custom agents as TOML files under ~/.codex/agents/ instead. Each agent's
# frontmatter name/description and Markdown body (its system prompt) are
# converted to a generated <name>.toml carrying a marker comment, so install
# and uninstall never touch files we did not generate. The `tools:` and
# `model:` frontmatter fields have no Codex equivalent and are dropped
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
  local agents_dir
  agents_dir="$(codex_agents_dir)"
  local cats
  cats="$(agent_categories)"
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
      if ((DRY_RUN)); then
        printf '[dry-run] write agent %s\n' "$dest"
        continue
      fi
      if [[ -e "$dest" ]] && ! grep -qF "$AGENT_MARKER" "$dest"; then
        printf '  WARN      %s exists and was not generated by us (skipping)\n' \
          "$dest" >&2
        continue
      fi
      mkdir -p "$agents_dir"
      printf '%s\n' "$toml" >"$dest.tmp.$$"
      mv "$dest.tmp.$$" "$dest"
      printf '  agent     %s -> %s\n' "$name" "$dest"
    done
  done <<<"$cats"
}

uninstall_codex_agents() {
  local agents_dir
  agents_dir="$(codex_agents_dir)"
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
      if ((DRY_RUN)); then
        printf '[dry-run] remove agent %s\n' "$dest"
        continue
      fi
      rm "$dest"
      printf '  removed   %s\n' "$dest"
    done
  done < <(agent_categories)
}

# Remove generated agent files whose subagent no longer exists in this repo
# (renamed or deleted): uninstall_codex_agents only walks the agents the repo
# currently ships, so those files would linger forever. The agents counterpart
# of prune_stale_skill_links. A source anywhere under plugins/*/agents/ keeps
# its file, so a --category run never prunes another category's agents; files
# without our marker are never touched.
prune_stale_codex_agents() {
  local agents_dir dest name
  agents_dir="$(codex_agents_dir)"
  [[ -d "$agents_dir" ]] || return 0
  for dest in "$agents_dir"/*.toml; do
    [[ -f "$dest" ]] || continue
    name="$(basename "$dest" .toml)"
    compgen -G "$REPO_ROOT/plugins/*/agents/$name.md" >/dev/null && continue
    grep -qF "$AGENT_MARKER" "$dest" || continue
    run rm "$dest"
    printf '  removed   %s (agent no longer in repo)\n' "$dest"
  done
}

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
    ((first)) || printf '\n'
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
    "$(render_instructions <<<"$fragments")" "$count instruction fragments"
}

# --- Path-scoped Claude rules ------------------------------------------------
#
# A fragment with `paths:` (comma-separated globs) goes to Claude as its own
# ~/.claude/rules/agents-<fragment>.md with `paths:` frontmatter, so it enters
# context only when Claude reads a matching file. The globs are written as a
# quoted YAML list: a bare `**/*.R` would parse as a YAML alias, and Claude
# loads a rule whose frontmatter does not parse unconditionally. The
# `managed-by:` line (ignored by Claude) marks the files this script owns;
# rules without it are never touched.

claude_rules_dir() { printf '%s/.claude/rules' "$HOME"; }

claude_rule_marker() { printf 'managed-by: fabiandistler/agents install.sh'; }

claude_rule_dest() {
  local name="${1##*/}"
  printf '%s/agents-%s' "$(claude_rules_dir)" "$name"
}

render_claude_rule() {
  local file="$1" paths glob globs
  paths="$(instruction_field "$file" paths)"
  printf -- '---\npaths:\n'
  # read -a, not an unquoted for-loop: the globs must not expand against $PWD.
  IFS=',' read -ra globs <<<"$paths"
  for glob in "${globs[@]}"; do
    glob="${glob#"${glob%%[![:space:]]*}"}"
    glob="${glob%"${glob##*[![:space:]]}"}"
    [[ -n "$glob" ]] && printf '  - "%s"\n' "$glob"
  done
  printf '%s\n---\n\n' "$(claude_rule_marker)"
  fragment_body "$file"
}

# Our rule files currently on disk, one path per line.
list_managed_claude_rules() {
  local file
  for file in "$(claude_rules_dir)"/agents-*.md; do
    [[ -f "$file" ]] || continue
    grep -qxF "$(claude_rule_marker)" "$file" && printf '%s\n' "$file"
  done
}

remove_claude_rule() {
  if ((DRY_RUN)); then
    printf '[dry-run] remove rule %s\n' "$1"
    return 0
  fi
  rm "$1"
  printf '  removed   %s\n' "$1"
}

# Write every path-scoped fragment as a rule file and drop managed rule files
# whose fragment is gone or lost its `paths:`. A foreign file already at a
# destination is left alone with a warning.
install_claude_rules() {
  local file dest content wanted=""
  for file in "$(instructions_dir)"/*.md; do
    [[ -f "$file" ]] || continue
    fragment_matches_target "$file" claude || continue
    fragment_is_claude_rule "$file" claude || continue
    dest="$(claude_rule_dest "$file")"
    wanted+="$dest"$'\n'
    content="$(render_claude_rule "$file")"
    if [[ -f "$dest" ]] && ! grep -qxF "$(claude_rule_marker)" "$dest"; then
      printf '  WARN      %s exists and is not managed by install.sh (leaving it untouched)\n' \
        "$dest" >&2
      continue
    fi
    if [[ -f "$dest" && "$(cat "$dest")" == "$content" ]]; then
      printf '  ok        %s\n' "$dest"
      continue
    fi
    if ((DRY_RUN)); then
      printf '[dry-run] write rule %s\n' "$dest"
      continue
    fi
    ensure_parent "$(claude_rules_dir)"
    write_file_atomic "$dest" "$content"
    printf '  updated   %s\n' "$dest"
  done
  while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    grep -qxF "$file" <<<"$wanted" || remove_claude_rule "$file"
  done < <(list_managed_claude_rules)
}

remove_claude_rules() {
  local file
  while IFS= read -r file; do
    [[ -n "$file" ]] && remove_claude_rule "$file"
  done < <(list_managed_claude_rules)
}

# Strip our instructions block from a target's file, leaving the rest.
remove_instructions() {
  local target="$1" dest
  dest="$(instruction_file_for "$target")" || return 1
  managed_block_remove "$dest" "$(instructions_begin_marker)" \
    "$(instructions_end_marker)" "instructions block"
}

# --- PR merge guard -----------------------------------------------------------
#
# Agents act under the user's GitHub account, so branch rules cannot stop them
# from merging; a pre-tool hook can. The decision and the hook entry both live
# in scripts/pr_merge_guard.py; this section only places the entry in each
# agent's user-level config. Claude's settings.json is JSON and cannot carry
# marker comments, so there our entry is identified by the script name in its
# command, and only that entry is ever added or removed.

merge_guard_command() {
  printf 'python3 "%s/scripts/pr_merge_guard.py" --harness %s' "$REPO_ROOT" "$1"
}

merge_guard_begin_marker() {
  printf '# >>> agents PR merge guard (managed by install.sh, do not edit) >>>'
}

merge_guard_end_marker() {
  printf '# <<< agents PR merge guard <<<'
}

opencode_merge_guard_link() { printf '%s/.config/opencode/plugins/pr-merge-guard.js' "$HOME"; }

# Print ~/.claude/settings.json with the guard entry added (mode install) or
# removed (mode remove). Exit 10: nothing to change; exit 1: not a JSON object.
claude_settings_with_merge_guard() {
  python3 - "$REPO_ROOT/scripts" "$1" "$2" "$(merge_guard_command claude)" <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from pr_merge_guard import with_claude_hook, without_claude_hook

mode, path, command = sys.argv[2], Path(sys.argv[3]), sys.argv[4]
try:
    settings = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
except ValueError:
    sys.exit(1)
if not isinstance(settings, dict):
    sys.exit(1)
wanted = with_claude_hook(settings, command) if mode == "install" else without_claude_hook(settings)
if wanted == settings:
    sys.exit(10)
print(json.dumps(wanted, indent=2))
PY
}

sync_claude_merge_guard() {
  local mode="$1" file="$HOME/.claude/settings.json" content status=0
  content="$(claude_settings_with_merge_guard "$mode" "$file")" || status=$?
  case "$status" in
    0) ;;
    10)
      [[ "$mode" == "install" ]] && printf '  ok        %s (PR merge guard hook)\n' "$file"
      return 0
      ;;
    *)
      printf '  WARN      %s is not a JSON object, leaving it untouched (PR merge guard)\n' \
        "$file" >&2
      return 0
      ;;
  esac
  if ((DRY_RUN)); then
    printf '[dry-run] %s PR merge guard hook in %s\n' "$mode" "$file"
    return 0
  fi
  ensure_parent "${file%/*}"
  write_file_atomic "$file" "$content"
  if [[ "$mode" == "install" ]]; then
    printf '  updated   %s (PR merge guard hook)\n' "$file"
  else
    printf '  removed   PR merge guard hook from %s\n' "$file"
  fi
}

install_merge_guard() {
  local target="$1" toml
  if ! command -v python3 >/dev/null 2>&1; then
    printf '  WARN      python3 not found; the PR merge guard needs it (skipping %s)\n' \
      "$target" >&2
    return 0
  fi
  case "$target" in
    claude) sync_claude_merge_guard install ;;
    codex)
      if ! toml="$(
        python3 - "$REPO_ROOT/scripts" "$(merge_guard_command codex)" <<'PY'
import sys

sys.path.insert(0, sys.argv[1])
from pr_merge_guard import codex_hook_toml

print(codex_hook_toml(sys.argv[2]))
PY
      )"; then
        printf '  WARN      cannot render the Codex PR merge guard hook (skipping)\n' >&2
        return 0
      fi
      managed_block_set "$(codex_config_path)" "$(merge_guard_begin_marker)" \
        "$(merge_guard_end_marker)" "$toml" "PR merge guard hook"
      ;;
    opencode)
      ensure_parent "${HOME}/.config/opencode/plugins"
      link_one "$REPO_ROOT/scripts/opencode/pr-merge-guard.js" "$(opencode_merge_guard_link)"
      ;;
  esac
}

uninstall_merge_guard() {
  case "$1" in
    claude)
      if command -v python3 >/dev/null 2>&1; then
        sync_claude_merge_guard remove
      else
        printf '  WARN      python3 not found; remove the pr_merge_guard.py hook from %s by hand\n' \
          "$HOME/.claude/settings.json" >&2
      fi
      ;;
    codex)
      managed_block_remove "$(codex_config_path)" "$(merge_guard_begin_marker)" \
        "$(merge_guard_end_marker)" "PR merge guard hook"
      ;;
    opencode)
      unlink_one "$REPO_ROOT/scripts/opencode/pr-merge-guard.js" "$(opencode_merge_guard_link)"
      ;;
  esac
}

run() {
  if ((DRY_RUN)); then
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

link_one() {
  local src="$1" dest="$2"
  if [[ -L "$dest" ]]; then
    local current
    current="$(readlink "$dest")"
    if [[ "$current" == "$src" ]]; then
      printf '  ok        %s -> %s\n' "$dest" "$src"
      return 0
    fi
    printf '  WARN      %s already symlinked to %s (skipping)\n' "$dest" "$current" >&2
    return 0
  fi
  if [[ -e "$dest" ]]; then
    printf '  WARN      %s exists and is not a symlink (skipping)\n' "$dest" >&2
    return 0
  fi
  run ln -s "$src" "$dest"
  printf '  linked    %s -> %s\n' "$dest" "$src"
}

unlink_one() {
  local src="$1" dest="$2"
  if [[ ! -L "$dest" ]]; then
    if [[ -e "$dest" ]]; then
      printf '  WARN      %s exists but is not a symlink (skipping)\n' "$dest" >&2
    fi
    return 0
  fi
  local current
  current="$(readlink "$dest")"
  if [[ "$current" != "$src" ]]; then
    printf '  WARN      %s points to %s (not ours, skipping)\n' "$dest" "$current" >&2
    return 0
  fi
  run rm "$dest"
  printf '  removed   %s\n' "$dest"
}

# Remove dangling symlinks a previous install left behind for skills that no
# longer exist in this repo (e.g. a skill that was renamed or deleted, or a
# router that was dismantled): --uninstall only walks the skills the repo
# currently ships, so those links would linger forever. Only broken symlinks
# whose target lies inside this repo's skills/ directory are removed; foreign
# links and anything that still resolves are left untouched.
prune_stale_skill_links() {
  local dir="$1" entry target
  [[ -d "$dir" ]] || return 0
  for entry in "$dir"/*; do
    [[ -L "$entry" ]] || continue
    [[ -e "$entry" ]] && continue
    target="$(readlink "$entry")"
    [[ "$target" == "$REPO_ROOT/skills/"* ]] || continue
    run rm "$entry"
    printf '  removed   %s (skill no longer in repo)\n' "$entry"
  done
}

# Earlier versions linked skills into OpenCode's agent directory
# (~/.config/opencode/agent), where the skill loader never looks. Remove any
# of our leftover symlinks from there — on install (migration) and uninstall
# alike. Symlinks not pointing into this repo are left untouched.
cleanup_opencode_legacy() {
  local skills="$1"
  local legacy_dir="$HOME/.config/opencode/agent"
  [[ -d "$legacy_dir" ]] || return 0
  while IFS= read -r skill; do
    [[ -z "$skill" ]] && continue
    local src="$REPO_ROOT/skills/$skill"
    local dest="$legacy_dir/$skill"
    [[ -L "$dest" ]] || continue
    [[ "$(readlink "$dest")" == "$src" ]] || continue
    run rm "$dest"
    printf '  removed   %s (legacy opencode location)\n' "$dest"
  done <<<"$skills"
}

cleanup_codex_prompts_legacy() {
  local skills="$1"
  local legacy_dir="$HOME/.codex/prompts"
  [[ -d "$legacy_dir" ]] || return 0
  while IFS= read -r skill; do
    [[ -z "$skill" ]] && continue
    local src="$REPO_ROOT/skills/$skill/SKILL.md"
    local dest="$legacy_dir/$skill.md"
    [[ -L "$dest" ]] || continue
    [[ "$(readlink "$dest")" == "$src" ]] || continue
    run rm "$dest"
    printf '  removed   %s (deprecated codex prompt)\n' "$dest"
  done <<<"$skills"
}

main() {
  local skills
  skills="$(list_skills)"
  if [[ -z "$skills" ]]; then
    echo "no skills found under $REPO_ROOT (env=$ENV, category=$CATEGORY)" >&2
    exit 1
  fi
  local routed
  routed="$(routed_categories)"
  [[ "$ENV" != "all" ]] && printf 'env filter: %s\n' "$ENV"
  [[ "$CATEGORY" != "all" ]] && printf 'category filter: %s\n' "$CATEGORY"

  while IFS= read -r target; do
    [[ -z "$target" ]] && continue
    local dest_dir cmd_dir="" cmd_dir_ready=0 codex_disabled_members=""
    dest_dir="$(target_dir_for "$target")"
    [[ "$target" != "codex" ]] && cmd_dir="$(target_command_dir_for "$target")"
    printf '%s: %s\n' "$target" "$dest_dir"
    if ((UNINSTALL == 0)); then
      ensure_parent "$dest_dir"
    fi
    while IFS= read -r skill; do
      local src dest activation category
      activation="$(skill_activation "$REPO_ROOT/skills/$skill/SKILL.md")"
      category="$(skill_category "$REPO_ROOT/skills/$skill/SKILL.md")"
      if [[ "$activation" == "command" && "$target" != "codex" ]]; then
        # User-invoked: link the single SKILL.md into the command directory.
        src="$REPO_ROOT/skills/$skill/SKILL.md"
        dest="$cmd_dir/$skill.md"
        if ((UNINSTALL == 0)) && ((cmd_dir_ready == 0)); then
          ensure_parent "$cmd_dir"
          cmd_dir_ready=1
        fi
      elif [[ "$activation" == "auto" && "$routed" == *" $category "* ]]; then
        # Auto member of a routed category: it is nested under the router's
        # members/ dir and loads lazily when routed to, so it is never linked
        # at top level. Command skills bypass routing (handled above for
        # non-codex; linked as skills for codex), so they are not skipped here.
        # Codex discovers the nested member recursively anyway, so record it to
        # disable by name in ~/.codex/config.toml further down.
        [[ "$target" == "codex" ]] && codex_disabled_members+="$skill"$'\n'
        # Migration: before this category was routed, the member was linked
        # flat here. That link still resolves, so prune_stale_skill_links (which
        # only removes broken ones) leaves it, and the member keeps registering
        # at top level — exactly what routing exists to prevent. Remove it on
        # both paths. unlink_one only touches a symlink pointing at our own
        # path, so foreign entries and real directories are left alone.
        unlink_one "$REPO_ROOT/skills/$skill" "$dest_dir/$skill"
        continue
      else
        # A normal auto skill, or the router itself (linked as a whole dir so
        # its nested members/ come along).
        src="$REPO_ROOT/skills/$skill"
        dest="$dest_dir/$skill"
      fi
      # A skill whose `targets:` field excludes this agent is never linked
      # here; unlinking instead keeps the tree self-healing when the field is
      # added to a skill that was already installed.
      if ((UNINSTALL)) || ! skill_matches_target "$REPO_ROOT/skills/$skill/SKILL.md" "$target"; then
        unlink_one "$src" "$dest"
      else
        link_one "$src" "$dest"
      fi
    done <<<"$skills"
    prune_stale_skill_links "$dest_dir"
    [[ -n "$cmd_dir" ]] && prune_stale_skill_links "$cmd_dir"
    if [[ "$target" == "codex" ]]; then
      cleanup_codex_prompts_legacy "$skills"
      # Runs on both paths: an upgrade must drop a managed block left by a
      # version that still registered the knowledge-base MCP servers.
      remove_legacy_codex_mcp
      prune_stale_codex_agents
      if ((UNINSTALL)); then
        uninstall_codex_agents
        remove_codex_member_overrides
      else
        install_codex_agents
        printf '%s' "$codex_disabled_members" | install_codex_member_overrides
      fi
    fi
    if [[ "$target" == "opencode" ]]; then
      cleanup_opencode_legacy "$skills"
    fi
    if ((INSTRUCTIONS)); then
      if ((UNINSTALL)); then
        remove_instructions "$target"
        if [[ "$target" == "claude" ]]; then remove_claude_rules; fi
      else
        install_instructions "$target"
        if [[ "$target" == "claude" ]]; then install_claude_rules; fi
      fi
    fi
    if ((MERGE_GUARD)); then
      if ((UNINSTALL)); then
        uninstall_merge_guard "$target"
      else
        install_merge_guard "$target"
      fi
    fi
  done < <(resolve_targets)
}

main
