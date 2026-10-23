#!/usr/bin/env bash
# Symlink the skills in this repo into the conventional install paths
# for popular coding agents. Idempotent; reversible via --uninstall.
#
# Usage:
#   ./install.sh --target=claude --instructions # instructions, rules, payloads + uv-init hook
#   ./install.sh --target=codex               # ~/.agents/skills/<skill>
#   ./install.sh --target=opencode            # ~/.config/opencode/skills/<skill>
#   ./install.sh --target=all                 # all of the above
#   ./install.sh --target=all --dry-run       # show what would happen
#   ./install.sh --target=all --uninstall     # remove symlinks owned by us
#   ./install.sh --target=opencode --env=chat # only chat skills
#   ./install.sh --target=codex  --env=coding # only coding skills
#   ./install.sh --target=codex --category=architecture,refactoring
#   ./install.sh --target=all --instructions   # also sync rules, payloads and the Claude uv-init hook
#   ./install.sh --target=all --merge-guard    # also block agent PR merges
#   ./install.sh --target=all --secret-guard   # also block credential reads
#
# Claude gets skills, command skills, subagents and the PR merge guard from the
# plugin marketplace only (claude plugin marketplace add fabiandistler/agents,
# then claude plugin install <category>@fabiandistler-agents and
# merge-guard@fabiandistler-agents). --target=claude therefore only syncs
# --instructions, and every claude run (install or uninstall) removes what
# earlier versions created: our links in ~/.claude/skills and
# ~/.claude/commands and the merge-guard entry in ~/.claude/settings.json.
# --env and --category do not apply to claude; passing either with a claude
# target prints one WARN line and changes nothing else.
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
# not model-triggered. For opencode they are linked into its command
# directory (~/.config/opencode/command) as <name>.md instead of the skills
# directory, keeping them out of the auto-trigger metadata. Codex custom
# prompts (~/.codex/prompts) are
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
# install additionally disables every nested member by path in
# ~/.codex/config.toml via a managed [[skills.config]] block (enabled = false),
# which drops them from the model's skill list; --uninstall removes the block.
#
# Codex skills go to ~/.agents/skills, Codex's documented user scope;
# ~/.codex/skills is kept by Codex only for backward compatibility. Other tools
# write to ~/.agents/skills too, so a name already taken there is reported and
# skipped, never overwritten. Codex install and uninstall both remove our own
# links (those pointing into this repo) from ~/.codex/skills.
#
# opencode also reads ~/.agents/skills and wants skill names unique across all
# its roots. A skill we already linked there gets no ~/.config/opencode/skills
# link (an old one is removed), whichever target runs first. Only skills
# missing there, through `targets:`, --env or --category, get their own
# opencode link. After uninstalling codex alone, re-run --target=opencode to
# give opencode its own links back. opencode reads ~/.claude/skills too, but we
# no longer link there; when the claude migration removes an old link, an
# installed opencode gets its own link to that skill instead.
#
# The codex target additionally installs the full plugins, not just the
# skills. Requires python3 (skipped with a warning otherwise); --uninstall
# reverses it. --env only filters skills; the plugin extras follow
# --category:
#   - Each selected plugin's subagents (plugins/<category>/agents/*.md) are
#     converted to Codex custom agents in ~/.codex/agents/<name>.toml.
#
# --instructions (off by default) composes always-on rules and pointers into
# each agent's global instruction file. It also installs the pointer targets in
# ~/.agents/instructions/. Fragments are ordered by their numeric filename
# prefix and may limit themselves to agents with a `targets:` frontmatter field.
# For Claude, fragments with `paths:` go to ~/.claude/rules/agents-<fragment>.md
# and load only for matching files. Codex gets the Python baseline by pointer;
# opencode gets the same pointer and keeps the R rules in its block. A Claude
# PreToolUse hook supplies the Python baseline for `uv init` before any Python
# file exists. Anything outside the managed markers is left untouched, so
# hand-written notes and @-imports survive; --uninstall strips our blocks and
# hooks and removes only unreferenced payloads. opencode
# gets its own ~/.config/opencode/AGENTS.md: it reads ~/.claude/CLAUDE.md only
# as a fallback when that file is missing, and opencode V2 not at all.
#
# --merge-guard (off by default) installs a model-free pre-tool hook that stops
# the agent from merging pull requests or enabling auto-merge; the human merges.
# The check is scripts/pr_merge_guard.py (needs python3 at hook time). codex: a
# managed [hooks] block in ~/.codex/config.toml (trust it once in Codex's
# /hooks); opencode: a plugin symlink in ~/.config/opencode/plugins/; claude:
# nothing, it prints the plugin command (the merge-guard plugin carries the
# hook). --merge-guard --uninstall removes exactly these, leaving other
# settings and hooks alone.
#
# --secret-guard (off by default) installs scripts/secret_read_guard.py the same
# way (secret-guard plugin for claude): it blocks reading credential files
# (.env, SSH keys, cloud and agent auth files) and dumping the environment.
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
GUARDS=""
TARGET=""
ENV="all"
CATEGORY="all"
# Skill filters given on the command line (they do not apply to claude).
FILTER_FLAGS=""

# Must match the category list in scripts/catalogue.py.
CATEGORIES="architecture refactoring ai-ml workflow communication personal"

# Print the header comment block: from line 2 up to the first line that is not
# a comment, minus that line. A hardcoded end line silently truncates as the
# block grows — this one cannot drift.
usage() { sed -n '2,/^[^#]/p' "$0" | sed '$d'; }

for arg in "$@"; do
  case "$arg" in
    --target=*) TARGET="${arg#--target=}" ;;
    --env=*)
      ENV="${arg#--env=}"
      [[ "$FILTER_FLAGS" == *--env* ]] || FILTER_FLAGS+=" --env"
      ;;
    --category=*)
      CATEGORY="${arg#--category=}"
      [[ "$FILTER_FLAGS" == *--category* ]] || FILTER_FLAGS+=" --category"
      ;;
    --dry-run) DRY_RUN=1 ;;
    --instructions) INSTRUCTIONS=1 ;;
    --merge-guard) GUARDS+=" merge" ;;
    --secret-guard) GUARDS+=" secret" ;;
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

if [[ -z "$CATEGORY" ]]; then
  echo "invalid --category= (expected one of: ${CATEGORIES// /|}|all)" >&2
  usage >&2
  exit 2
fi

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
    codex) printf '%s/.agents/skills\n' "$HOME" ;;
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

# Set a complete file this installer owns. The caller renders content and
# sends it on stdin; this function guards ownership and writes only changes.
# The label names the kind of file and selects its ownership marker; `name`
# picks the marker for instruction payloads, which differ by file type.
owned_file_set() {
  local target="$1" label="$2" name="${3:-}" marker content
  case "$label" in
    agent) marker="$AGENT_MARKER" ;;
    rule) marker="$(claude_rule_marker)" ;;
    instruction-payload) marker="$(instruction_payload_marker_for "$name")" ;;
    *)
      printf 'owned_file_set: unknown label %s\n' "$label" >&2
      return 2
      ;;
  esac
  content="$(cat)"
  if [[ -L "$target" ]] || { [[ -e "$target" ]] && [[ ! -f "$target" ]]; } ||
    { [[ -e "$target" ]] && ! grep -qxF "$marker" "$target" 2>/dev/null; }; then
    printf '  WARN      %s exists and is not managed by install.sh (leaving it untouched)\n' \
      "$target" >&2
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
  write_file_atomic "$target" "$content"
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
  local before="" after begin_count
  [[ -f "$file" ]] && before="$(cat "$file")"
  if ! block_markers_balanced "$begin" "$end" <<<"$before"; then
    warn_unbalanced_markers "$file" "$what"
    return 0
  fi
  local block="$begin"$'\n'"$body"$'\n'"$end"
  begin_count="$(grep -Fxc "$begin" <<<"$before" || true)"
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
    printf '[dry-run] remove %s\n' "$file"
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
      printf '[dry-run] remove %s\n' "$venv"
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
# member in ~/.codex/config.toml via a [[skills.config]] entry (enabled =
# false), which drops it from the model's skill list. The entry selects the
# member by `path`, the only selector the Codex config reference documents.
# Codex canonicalizes both sides, so the repo path matches the member it
# discovers through the router's symlinks, and a foreign skill that happens to
# share the member's name stays enabled. The block is marker-delimited so
# install and uninstall stay idempotent and never touch config we do not own.

skill_override_begin_marker() {
  printf '# >>> agents routed-member skill overrides (managed by install.sh, do not edit) >>>'
}

skill_override_end_marker() {
  printf '# <<< agents routed-member skill overrides <<<'
}

# Render one [[skills.config]] disable table per member name read on stdin,
# selecting the member by the path of its SKILL.md in this repo.
render_skill_override_toml() {
  local name first=1 root
  # The clone path lands in a TOML basic string, so escape \ and ".
  root="${REPO_ROOT//\\/\\\\}"
  root="${root//\"/\\\"}"
  while IFS= read -r name; do
    [[ -n "$name" ]] || continue
    if [[ ! "$name" =~ ^[A-Za-z0-9_-]+$ ]]; then
      printf '  WARN      skill name %q is not a bare identifier (skipping override)\n' \
        "$name" >&2
      continue
    fi
    ((first)) || printf '\n'
    first=0
    printf '[[skills.config]]\npath = "%s/skills/%s/SKILL.md"\nenabled = false\n' \
      "$root" "$name"
  done
}

# Strip our override block from ~/.codex/config.toml (leaving foreign config).
remove_codex_member_overrides() {
  managed_block_remove "$(codex_config_path)" "$(skill_override_begin_marker)" \
    "$(skill_override_end_marker)" "routed-member skill overrides"
}

# Print the nested members (one per line) of every router Codex sees under
# dest_dir: one linked by this run (named in the newline-separated `skills`)
# or one whose link a previous run left in place. Deriving the set from the
# installed routers rather than from the --category filter keeps a narrower
# re-run from re-enabling the members of routers it did not touch (#562).
codex_routed_members() {
  local dest_dir="$1" skills="$2" d router member
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    [[ "$(skill_activation "$d/SKILL.md")" == "router" ]] || continue
    router="$(basename "$d")"
    if ! { [[ $'\n'"$skills"$'\n' == *$'\n'"$router"$'\n'* ]] &&
      skill_matches_target "$d/SKILL.md" codex; } &&
      [[ "$(readlink "$dest_dir/$router" 2>/dev/null)" != "$REPO_ROOT/skills/$router" ]]; then
      continue
    fi
    for member in "$d"members/*; do
      [[ -e "$member" ]] && printf '%s\n' "$(basename "$member")"
    done
  done
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
      owned_file_set "$dest" agent <<<"$toml"
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
        printf '[dry-run] remove %s\n' "$dest"
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
    ((DRY_RUN)) || printf '  removed   %s (agent no longer in repo)\n' "$dest"
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
    printf '[dry-run] remove %s\n' "$1"
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
    owned_file_set "$dest" rule <<<"$content"
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

python_init_hook_command() {
  printf 'python3 "%s/.agents/instructions/python_init_context.py" --baseline "%s/.agents/instructions/30-python.md"' \
    "$HOME" "$HOME"
}

# Print ~/.claude/settings.json with the Python uv-init context hook installed.
# Exit 1 when the file is unreadable/invalid or has an incompatible hooks shape.
claude_settings_with_python_hook() {
  python3 - "$REPO_ROOT/scripts" "$1" "$2" <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from python_init_context import with_claude_hook

path = Path(sys.argv[2])
try:
    settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
except (OSError, ValueError):
    sys.exit(1)
if not isinstance(settings, dict):
    sys.exit(1)
try:
    wanted = with_claude_hook(settings, sys.argv[3])
except (TypeError, ValueError):
    sys.exit(1)
print(json.dumps(wanted, indent=2))
PY
}

# Print ~/.claude/settings.json without our Python hook. Exit 10 when absent.
claude_settings_without_python_hook() {
  python3 - "$REPO_ROOT/scripts" "$1" <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from python_init_context import without_claude_hook

path = Path(sys.argv[2])
try:
    settings = json.loads(path.read_text(encoding="utf-8"))
except (OSError, ValueError):
    sys.exit(1)
if not isinstance(settings, dict):
    sys.exit(1)
wanted = without_claude_hook(settings)
if wanted == settings:
    sys.exit(10)
print(json.dumps(wanted, indent=2))
PY
}

install_claude_python_hook() {
  local file="$HOME/.claude/settings.json" command content
  if ! instruction_payload_available 30-python.md ||
    ! instruction_payload_available python_init_context.py; then
    printf '  WARN      cannot install the Claude uv-init context hook because an instruction payload is unavailable\n' >&2
    return 0
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    printf '  WARN      python3 not found; cannot install the Claude uv-init context hook\n' >&2
    return 0
  fi
  if [[ -L "$file" ]]; then
    printf '  WARN      %s is a symlink, leaving it untouched (Python uv-init context hook)\n' \
      "$file" >&2
    return 0
  fi
  command="$(python_init_hook_command)"
  if ! content="$(claude_settings_with_python_hook "$file" "$command")"; then
    printf '  WARN      %s is not a compatible JSON object, leaving it untouched (Python uv-init context hook)\n' \
      "$file" >&2
    return 0
  fi
  if [[ -f "$file" && "$(cat "$file")" == "$content" ]]; then
    printf '  ok        %s (Python uv-init context hook)\n' "$file"
    return 0
  fi
  if ((DRY_RUN)); then
    printf '[dry-run] write %s\n' "$file"
    return 0
  fi
  ensure_parent "${file%/*}"
  write_file_atomic "$file" "$content"
  printf '  updated   %s (Python uv-init context hook)\n' "$file"
}

remove_claude_python_hook() {
  local file="$HOME/.claude/settings.json" content status=0
  [[ -f "$file" ]] && grep -qF python_init_context.py "$file" || return 0
  if [[ -L "$file" ]]; then
    printf '  WARN      %s is a symlink, leaving it untouched (Python uv-init context hook)\n' \
      "$file" >&2
    return 0
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    printf '  WARN      python3 not found; remove the Python uv-init context hook from %s by hand\n' \
      "$file" >&2
    return 0
  fi
  content="$(claude_settings_without_python_hook "$file")" || status=$?
  case "$status" in
    0) ;;
    10) return 0 ;;
    *)
      printf '  WARN      %s is not a JSON object, leaving it untouched (Python uv-init context hook)\n' \
        "$file" >&2
      return 0
      ;;
  esac
  if ((DRY_RUN)); then
    printf '[dry-run] remove %s\n' "$file"
    return 0
  fi
  write_file_atomic "$file" "$content"
  printf '  removed   Python uv-init context hook from %s\n' "$file"
}

# --- Pre-tool guards (PR merge guard, secret read guard) ----------------------
#
# Agents act under the user's GitHub account, so branch rules cannot stop them
# from merging; a pre-tool hook can. The decision and the hook entry both live
# in scripts/pr_merge_guard.py; this section only places the entry in each
# agent's user-level config. Claude gets the guard from the merge-guard plugin
# instead; earlier versions wrote it into ~/.claude/settings.json, and the
# Claude migration below removes that entry. settings.json is JSON and cannot
# carry marker comments, so our entry is identified by the script name in its
# command, and only that entry is ever removed.
#
# The secret read guard (scripts/secret_read_guard.py) is installed the same
# way: it keeps credential files and environment dumps out of the agent's
# context. Claude gets it from the secret-guard plugin.

# A guard is named by its key (merge, secret); the script, plugin and opencode
# adapter names derive from it.
guard_script() {
  case "$1" in
    merge) printf 'pr_merge_guard' ;;
    secret) printf 'secret_read_guard' ;;
  esac
}

guard_label() {
  case "$1" in
    merge) printf 'PR merge guard' ;;
    secret) printf 'secret read guard' ;;
  esac
}

guard_plugin() { printf '%s-guard@fabiandistler-agents' "$1"; }

guard_opencode_file() {
  local script
  script="$(guard_script "$1")"
  printf '%s.js' "${script//_/-}"
}

guard_command() {
  printf 'python3 "%s/scripts/%s.py" --harness %s' "$REPO_ROOT" "$(guard_script "$1")" "$2"
}

guard_begin_marker() {
  printf '# >>> agents %s (managed by install.sh, do not edit) >>>' "$(guard_label "$1")"
}

guard_end_marker() { printf '# <<< agents %s <<<' "$(guard_label "$1")"; }

opencode_guard_link() {
  printf '%s/.config/opencode/plugins/%s' "$HOME" "$(guard_opencode_file "$1")"
}

MARKETPLACE="fabiandistler/agents"

# Print ~/.claude/settings.json without the guard entry. Exit 10: nothing to
# change; exit 1: not a JSON object.
claude_settings_without_merge_guard() {
  python3 - "$REPO_ROOT/scripts" "$1" <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from pr_merge_guard import without_claude_hook

path = Path(sys.argv[2])
try:
    settings = json.loads(path.read_text(encoding="utf-8"))
except ValueError:
    sys.exit(1)
if not isinstance(settings, dict):
    sys.exit(1)
wanted = without_claude_hook(settings)
if wanted == settings:
    sys.exit(10)
print(json.dumps(wanted, indent=2))
PY
}

# Drop the guard entry an earlier version wrote into ~/.claude/settings.json.
remove_claude_settings_merge_guard() {
  local file="$HOME/.claude/settings.json" content status=0
  [[ -f "$file" ]] && grep -qF pr_merge_guard.py "$file" || return 0
  if ! command -v python3 >/dev/null 2>&1; then
    printf '  WARN      python3 not found; remove the pr_merge_guard.py hook from %s by hand\n' \
      "$file" >&2
    return 0
  fi
  content="$(claude_settings_without_merge_guard "$file")" || status=$?
  case "$status" in
    0) ;;
    10) return 0 ;;
    *)
      printf '  WARN      %s is not a JSON object, leaving it untouched (PR merge guard)\n' \
        "$file" >&2
      return 0
      ;;
  esac
  if ((DRY_RUN)); then
    printf '[dry-run] remove %s\n' "$file"
    return 0
  fi
  write_file_atomic "$file" "$content"
  printf '  removed   PR merge guard hook from %s (now the merge-guard plugin)\n' "$file"
}

install_guard() {
  local guard="$1" target="$2" label toml
  label="$(guard_label "$guard")"
  if [[ "$target" == "claude" ]]; then
    printf '  note      claude: claude plugin install %s\n' "$(guard_plugin "$guard")"
    return 0
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    printf '  WARN      python3 not found; the %s needs it (skipping %s)\n' \
      "$label" "$target" >&2
    return 0
  fi
  case "$target" in
    codex)
      if ! toml="$(
        python3 - "$REPO_ROOT/scripts" "$(guard_script "$guard")" \
          "$(guard_command "$guard" codex)" <<'PY'
import importlib
import sys

sys.path.insert(0, sys.argv[1])
from pr_merge_guard import codex_hook_toml

guard = importlib.import_module(sys.argv[2])
print(codex_hook_toml(sys.argv[3], guard.HOOK_MATCHER, guard.HOOK_STATUS))
PY
      )"; then
        printf '  WARN      cannot render the Codex %s hook (skipping)\n' "$label" >&2
        return 0
      fi
      managed_block_set "$(codex_config_path)" "$(guard_begin_marker "$guard")" \
        "$(guard_end_marker "$guard")" "$toml" "$label hook"
      ;;
    opencode)
      ensure_parent "${HOME}/.config/opencode/plugins"
      link_one "$REPO_ROOT/scripts/opencode/$(guard_opencode_file "$guard")" \
        "$(opencode_guard_link "$guard")"
      ;;
  esac
}

uninstall_guard() {
  local guard="$1"
  case "$2" in
    claude)
      printf '  note      claude: claude plugin uninstall %s\n' "$(guard_plugin "$guard")"
      ;;
    codex)
      managed_block_remove "$(codex_config_path)" "$(guard_begin_marker "$guard")" \
        "$(guard_end_marker "$guard")" "$(guard_label "$guard") hook"
      ;;
    opencode)
      unlink_one "$REPO_ROOT/scripts/opencode/$(guard_opencode_file "$guard")" \
        "$(opencode_guard_link "$guard")"
      ;;
  esac
}

run() {
  if ((DRY_RUN)); then
    case "$1" in
      rm) printf '[dry-run] remove %s\n' "$2" ;;
      ln) printf '[dry-run] link %s\n' "$4" ;;
      mkdir) return 0 ;;
      *)
        printf 'run: unsupported dry-run operation\n' >&2
        return 2
        ;;
    esac
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
  if ((DRY_RUN)); then
    PLANNED_LINKS+="$dest"$'\n'
    return 0
  fi
  printf '  linked    %s -> %s\n' "$dest" "$src"
}

# Links a dry-run planned but did not create, one per line, so a later target
# in the same dry-run sees the state the real run would leave.
PLANNED_LINKS=""

# True if dest is our link to src, or this dry-run planned it.
our_link_at() {
  local src="$1" dest="$2"
  [[ "$(readlink "$dest" 2>/dev/null)" == "$src" ]] ||
    [[ $'\n'"$PLANNED_LINKS" == *$'\n'"$dest"$'\n'* ]]
}

# --- Skill roots opencode shares ----------------------------------------------
#
# opencode loads skills from ~/.config/opencode/skills, ~/.claude/skills and
# ~/.agents/skills (https://opencode.ai/docs/skills), and it expects every
# name to be unique across them. So a skill whose link already sits in the
# codex skills root gets no opencode link of its own, and a duplicate we
# created earlier is removed. A skill the codex root lacks (a `targets:` field
# excluding codex, or a narrower --env or --category for codex) still gets its
# own opencode link. ~/.claude/skills is no shared root any more: Claude takes
# its skills from the plugins, and the claude migration empties that dir of our
# links (handing each one to opencode, see migrate_claude_to_plugins).

opencode_skills_dir() { target_dir_for opencode; }

# Print the codex skills root if it holds our link to src; fail otherwise.
opencode_shared_root_for() {
  local src="$1" root
  root="$(target_dir_for codex)"
  our_link_at "$src" "$root/${src##*/}" || return 1
  printf '%s' "$root"
}

# Remove our opencode link to src, if any: opencode reads src from `root`.
drop_opencode_duplicate() {
  local src="$1" root="$2" dest
  dest="$(opencode_skills_dir)/${src##*/}"
  [[ "$(readlink "$dest" 2>/dev/null)" == "$src" ]] || return 0
  run rm "$dest"
  ((DRY_RUN)) || printf '  removed   %s (opencode reads it from %s)\n' "$dest" "$root"
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
  ((DRY_RUN)) && return 0
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
    ((DRY_RUN)) || printf '  removed   %s (skill no longer in repo)\n' "$entry"
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
    ((DRY_RUN)) || printf '  removed   %s (legacy opencode location)\n' "$dest"
  done <<<"$skills"
}

# Earlier versions linked Codex skills into ~/.codex/skills, which Codex still
# reads for backward compatibility; left there, every skill would load twice
# next to ~/.agents/skills. Remove all our links from there, whatever --env or
# --category says, on install (migration) and uninstall alike. A link counts as
# ours when its target lies inside this repo's skills/ directory, so links
# other tools put there are never touched.
cleanup_codex_skills_legacy() {
  local legacy_dir="$HOME/.codex/skills" entry
  [[ -d "$legacy_dir" ]] || return 0
  for entry in "$legacy_dir"/*; do
    [[ -L "$entry" ]] || continue
    [[ "$(readlink "$entry")" == "$REPO_ROOT/skills/"* ]] || continue
    run rm "$entry"
    ((DRY_RUN)) || printf '  removed   %s (deprecated codex skills dir)\n' "$entry"
  done
}

# Claude gets skills, command skills, subagents and the merge guard from the
# plugin marketplace (#567). Earlier versions linked skills into
# ~/.claude/skills, command skills into ~/.claude/commands, and wrote the merge
# guard into ~/.claude/settings.json; next to the plugins, every skill would
# load twice (/tldr and /communication:tldr). Remove what we created, on install
# and uninstall alike and regardless of --env/--category. Only symlinks into
# this repo's skills/ (dangling ones included) are touched.
# An earlier opencode install may have skipped a skill because opencode read it
# from ~/.claude/skills. When opencode is installed (its skills dir exists),
# each removed skill link is handed over: opencode gets its own link unless the
# codex root still shares it.
migrate_claude_to_plugins() {
  local dir entry src
  for dir in "$(target_dir_for claude)" "$(target_command_dir_for claude)"; do
    [[ -d "$dir" ]] || continue
    for entry in "$dir"/*; do
      [[ -L "$entry" ]] || continue
      src="$(readlink "$entry")"
      [[ "$src" == "$REPO_ROOT/skills/"* ]] || continue
      run rm "$entry"
      ((DRY_RUN)) || printf '  removed   %s (now in the Claude plugins)\n' "$entry"
      if [[ "$dir" == "$(target_dir_for claude)" && -f "$src/SKILL.md" ]]; then
        hand_skill_to_opencode "$src"
      fi
    done
  done
  remove_claude_settings_merge_guard
}

# Give opencode its own link to a skill it used to read from ~/.claude/skills.
hand_skill_to_opencode() {
  local src="$1" opencode_dir
  opencode_dir="$(opencode_skills_dir)"
  [[ -d "$opencode_dir" ]] || return 0
  skill_matches_target "$src/SKILL.md" opencode || return 0
  opencode_shared_root_for "$src" >/dev/null && return 0
  link_one "$src" "$opencode_dir/${src##*/}"
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
    ((DRY_RUN)) || printf '  removed   %s (deprecated codex prompt)\n' "$dest"
  done <<<"$skills"
}

# Link (or, with --uninstall, unlink) the selected skills for one target, then
# prune links to skills the repo no longer ships.
sync_skill_links() {
  local target="$1" skills="$2" routed="$3"
  local dest_dir cmd_dir="" cmd_dir_ready=0 shared_root
  dest_dir="$(target_dir_for "$target")"
  [[ "$target" != "codex" ]] && cmd_dir="$(target_command_dir_for "$target")"
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
      # Codex discovers the nested member recursively anyway; it is disabled
      # by path in ~/.codex/config.toml further down.
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
    elif [[ "$target" == "opencode" && "$dest" == "$dest_dir/"* ]] &&
      shared_root="$(opencode_shared_root_for "$src")"; then
      drop_opencode_duplicate "$src" "$shared_root"
      if ((DRY_RUN)) && [[ "$(readlink "$dest" 2>/dev/null)" == "$src" ]]; then
        continue
      fi
      printf '  shared    %s (opencode reads it from %s)\n' "$dest" "$shared_root"
    else
      link_one "$src" "$dest"
      # Run in either order, claude/codex and opencode end up with one link.
      if [[ "$target" != "opencode" && "$dest" == "$dest_dir/"* ]] &&
        our_link_at "$src" "$dest"; then
        drop_opencode_duplicate "$src" "$dest_dir"
      fi
    fi
  done <<<"$skills"
  # opencode loses the skills it read from this root; tell the user how to
  # give it links of its own. --target=all removes opencode's links anyway.
  if ((UNINSTALL)) && [[ "$TARGET" != "all" && "$target" != "opencode" ]] &&
    [[ -d "$(opencode_skills_dir)" ]]; then
    printf '  note      opencode read skills from %s; re-run --target=opencode to link them for it\n' \
      "$dest_dir" >&2
  fi
  prune_stale_skill_links "$dest_dir"
  [[ -n "$cmd_dir" ]] && prune_stale_skill_links "$cmd_dir"
  return 0
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
  if [[ -n "$FILTER_FLAGS" && ("$TARGET" == "claude" || "$TARGET" == "all") ]]; then
    printf '  WARN      %s: no effect for claude (its skills come from the plugin marketplace)\n' \
      "${FILTER_FLAGS# }" >&2
  fi

  if ((INSTRUCTIONS && UNINSTALL == 0)); then
    install_instruction_payloads
  fi

  while IFS= read -r target; do
    [[ -z "$target" ]] && continue
    if [[ "$target" == "claude" ]]; then
      printf 'claude: skills, commands and subagents come from the plugin marketplace\n'
      migrate_claude_to_plugins
      ((UNINSTALL)) || printf '  note      claude: claude plugin marketplace add %s\n' "$MARKETPLACE"
    else
      printf '%s: %s\n' "$target" "$(target_dir_for "$target")"
      sync_skill_links "$target" "$skills" "$routed"
    fi
    if [[ "$target" == "codex" ]]; then
      cleanup_codex_skills_legacy
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
        codex_routed_members "$(target_dir_for codex)" "$skills" | install_codex_member_overrides
      fi
    fi
    if [[ "$target" == "opencode" ]]; then
      cleanup_opencode_legacy "$skills"
    fi
    if ((INSTRUCTIONS)); then
      if ((UNINSTALL)); then
        remove_instructions "$target"
        if [[ "$target" == "claude" ]]; then
          remove_claude_rules
          remove_claude_python_hook
        fi
      else
        install_instructions "$target"
        if [[ "$target" == "claude" ]]; then
          install_claude_rules
          install_claude_python_hook
        fi
      fi
    fi
    for guard in $GUARDS; do
      if ((UNINSTALL)); then
        uninstall_guard "$guard" "$target"
      else
        install_guard "$guard" "$target"
      fi
    done
  done < <(resolve_targets)

  if ((INSTRUCTIONS && UNINSTALL)); then
    prune_instruction_payloads
  fi
}

main
