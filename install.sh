#!/usr/bin/env bash
# Symlink the skills in this repo into the conventional install paths
# for popular coding agents. Idempotent; reversible via --uninstall.
#
# Usage:
#   ./install.sh --target=claude --instructions # instructions, rules, payloads + uv-init hook
#   ./install.sh --target=codex               # ~/.agents/skills/<skill>
#   ./install.sh --target=opencode            # ~/.config/opencode/skills/<skill>
#   ./install.sh --target=all                 # all of the above
#   ./install.sh --target=detected            # installed commands/config dirs
#   ./install.sh --target=all --dry-run       # show what would happen
#   ./install.sh --target=all --uninstall     # remove symlinks owned by us
#   ./install.sh --target=opencode --env=chat # only chat skills
#   ./install.sh --target=codex  --env=coding # only coding skills
#   ./install.sh --target=codex --category=architecture,refactoring
#   ./install.sh --target=all --instructions   # also sync rules, payloads and the Claude uv-init hook
#   ./install.sh --target=all --merge-guard    # also block agent PR merges
#   ./install.sh --target=all --secret-guard   # also block credential reads
#   ./install.sh --target=all --check           # report managed-file drift
#   ./install.sh --target=all --check --output drift.tsv
#   ./install.sh --update                        # replay the last install
#   ./install.sh --target=all --git-hook          # update after merge/rewrite
#   ./install.sh --update --dry-run              # preview the replay
#   ./install.sh --uninstall --git-hook           # remove this clone's hooks
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
# not model-triggered. OpenCode uses each skill's opencode/slash and
# opencode/autoinvoke metadata, so these skills stay in the ordinary skills
# directory. Codex custom prompts (~/.codex/prompts) are deprecated, so under
# Codex these skills install into the skills directory like any other; their
# agents/openai.yaml sidecar (policy.allow_implicit_invocation: false) keeps
# Codex from auto-triggering them. --uninstall reverses this, and old Codex and
# OpenCode command links are cleaned up during migration.
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
# Codex and OpenCode also install selected plugin subagents from
# plugins/<category>/agents/*.md. Both render from the same source parser;
# Codex writes TOML under ~/.codex/agents/, while OpenCode writes Markdown under
# ~/.config/opencode/agents/. Requires python3 (skipped with a warning
# otherwise); --uninstall removes only marker-owned outputs. --env only filters
# skills; plugin agents follow --category.
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
# --check calculates the selected managed state without writing. It exits 0 when
# clean, 3 when drift is found and 2 for invalid options. --output FILE writes
# TSV instead of only printing the default summary; it requires --check. The
# checker also flags Codex hooks that do not have a matching trusted hash.
#
# --update replays the last successful install from
# ${XDG_STATE_HOME:-~/.local/state}/fabiandistler-agents/install.json. It exits 4
# when no state exists; first install with --target=claude|codex|opencode|all.
# Writes during --update re-check their file right before writing and leave it
# alone if it changed in between.
# --git-hook installs marker-owned post-merge and post-rewrite hooks in this
# clone. Each checks saved install state before replaying it with --update.
# --target=detected selects agents with an installed command or config directory.
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
CHECK_MODE=0
UPDATE_MODE=0
GIT_HOOK=0
GIT_HOOK_MARKER='# managed-by: fabiandistler/agents install.sh'
CHECK_OUTPUT=""
CHECK_OUTPUT_SET=0
CHECK_ROWS=""
CHECK_CURRENT_TARGET=""
RESOLVED_TARGETS=""
OLD_REPO_ROOT=""
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

usage() {
  cat <<'EOF'
Usage:
  ./install.sh --target=claude|codex|opencode|all|detected [options]
  ./install.sh --update [--dry-run] [--check [--output FILE]]
  ./install.sh --uninstall --git-hook

Options:
  --env=coding|chat|all        Filter skills (default: all)
  --category=NAME[,NAME...]    Filter skill categories
  --instructions               Install shared instruction rules
  --merge-guard                Install the PR merge guard
  --secret-guard               Install the secret read guard
  --dry-run                    Preview changes without writing
  --uninstall                  Remove selected managed files
  --check                      Report drift (0 clean, 3 drift)
  --output FILE|--output=FILE  Write the --check TSV report
  --update                     Replay the saved install (4: no saved state)
  --git-hook                   Install this clone's update hooks
  -h, --help                   Show this help

Exit codes: 0 success, 1 operational failure, 2 usage error,
            3 --check found drift, 4 --update has no saved install.

Examples:
  ./install.sh --target=all --instructions --dry-run
  ./install.sh --target=detected --check --output /tmp/agents-drift.tsv
EOF
}

install_state_file() {
  local state_home="${XDG_STATE_HOME:-$HOME/.local/state}"
  printf '%s/fabiandistler-agents/install.json' "${state_home%/}"
}

load_install_state() {
  local file reader_pid status targets_csv stored_env stored_category stored_instructions \
    stored_merge stored_secret stored_repo_root target
  file="$(install_state_file)"
  if [[ -L "$file" ]] || { [[ -e "$file" ]] && [[ ! -f "$file" ]]; }; then
    printf 'saved install state is not a regular file: %s\n' "$file" >&2
    return 1
  fi
  if [[ ! -f "$file" ]]; then
    printf 'no saved install state at %s; install once with --target=claude|codex|opencode|all before --update\n' \
      "$file" >&2
    return 4
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required to read --update state" >&2
    return 1
  fi
  exec 3< <(
    python3 - "$file" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as state_file:
        state = json.load(state_file)
    targets = state["targets"]
    environment = state["env"]
    category = state["category"]
    instructions = state["instructions"]
    merge_guard = state["merge_guard"]
    secret_guard = state["secret_guard"]
    repo_root = state["repo_root"]
    if (
        not isinstance(targets, list)
        or not targets
        or any(target not in {"claude", "codex", "opencode"} for target in targets)
        or len(set(targets)) != len(targets)
        or not isinstance(environment, str)
        or "\0" in environment
        or not isinstance(category, str)
        or "\0" in category
        or type(instructions) is not bool
        or type(merge_guard) is not bool
        or type(secret_guard) is not bool
        or not isinstance(repo_root, str)
        or not repo_root.startswith("/")
        or "\0" in repo_root
    ):
        raise ValueError("invalid fields")
    values = [
        ",".join(targets),
        environment,
        category,
        "1" if instructions else "0",
        "1" if merge_guard else "0",
        "1" if secret_guard else "0",
        repo_root,
    ]
    sys.stdout.buffer.write("\0".join(values).encode("utf-8") + b"\0")
except (OSError, UnicodeError, ValueError, KeyError, TypeError):
    sys.stderr.write("saved install state is invalid\n")
    sys.exit(1)
PY
  )
  reader_pid=$!
  if ! IFS= read -r -d '' targets_csv <&3 ||
    ! IFS= read -r -d '' stored_env <&3 ||
    ! IFS= read -r -d '' stored_category <&3 ||
    ! IFS= read -r -d '' stored_instructions <&3 ||
    ! IFS= read -r -d '' stored_merge <&3 ||
    ! IFS= read -r -d '' stored_secret <&3 ||
    ! IFS= read -r -d '' stored_repo_root <&3; then
    exec 3<&-
    wait "$reader_pid" || true
    echo "saved install state is invalid" >&2
    return 1
  fi
  exec 3<&-
  if wait "$reader_pid"; then
    :
  else
    status=$?
    return "$status"
  fi

  ENV="$stored_env"
  CATEGORY="$stored_category"
  INSTRUCTIONS="$stored_instructions"
  GUARDS=""
  [[ "$stored_merge" == 1 ]] && GUARDS+=" merge"
  [[ "$stored_secret" == 1 ]] && GUARDS+=" secret"
  OLD_REPO_ROOT="$stored_repo_root"
  RESOLVED_TARGETS=""
  IFS=',' read -ra _resolved_targets <<<"$targets_csv"
  for target in "${_resolved_targets[@]}"; do
    RESOLVED_TARGETS+="$target"$'\n'
  done
  if [[ "$targets_csv" == "claude,codex,opencode" ]]; then
    TARGET=all
  elif [[ "$targets_csv" == *','* ]]; then
    TARGET=resolved
  else
    TARGET="$targets_csv"
  fi
  [[ "$ENV" == all ]] || FILTER_FLAGS+=" --env"
  [[ "$CATEGORY" == all ]] || FILTER_FLAGS+=" --category"
}

json_quote() {
  local value="$1" escaped="" character escaped_character code index
  for ((index = 0; index < ${#value}; index++)); do
    character="${value:index:1}"
    case "$character" in
      '"') escaped+='\\"' ;;
      \\) escaped+='\\\\' ;;
      $'\b') escaped+='\\b' ;;
      $'\f') escaped+='\\f' ;;
      $'\n') escaped+='\\n' ;;
      $'\r') escaped+='\\r' ;;
      $'\t') escaped+='\\t' ;;
      *)
        printf -v code '%d' "'$character"
        if ((code < 32)); then
          printf -v escaped_character '\\u%04x' "$code"
          escaped+="$escaped_character"
        else
          escaped+="$character"
        fi
        ;;
    esac
  done
  printf '"%s"' "$escaped"
}

write_install_state() {
  local file dir target targets_json="[" separator="" content tmp before="" had_file=0 current
  [[ -n "$RESOLVED_TARGETS" ]] || RESOLVED_TARGETS="$(resolve_targets)"
  while IFS= read -r target; do
    [[ -n "$target" ]] || continue
    targets_json+="$separator$(json_quote "$target")"
    separator=,
  done <<<"$RESOLVED_TARGETS"
  targets_json+="]"
  file="$(install_state_file)"
  dir="${file%/*}"
  if [[ -L "$file" ]] || { [[ -e "$file" ]] && [[ ! -f "$file" ]]; }; then
    printf 'refusing to replace non-regular install state path: %s\n' "$file" >&2
    return 1
  fi
  if [[ -f "$file" ]]; then
    before="$(cat "$file")"
    had_file=1
  fi
  ensure_parent "$dir"
  content="{\"targets\":$targets_json,\"env\":$(json_quote "$ENV"),\"category\":$(json_quote "$CATEGORY"),\"instructions\":$( ((INSTRUCTIONS)) && printf true || printf false),\"merge_guard\":$([[ "$GUARDS" == *' merge'* ]] && printf true || printf false),\"secret_guard\":$([[ "$GUARDS" == *' secret'* ]] && printf true || printf false),\"repo_root\":$(json_quote "$REPO_ROOT") }"
  tmp="$file.tmp.$$"
  if [[ -e "$tmp" || -L "$tmp" ]]; then
    printf 'refusing to replace temporary install state path: %s\n' "$tmp" >&2
    return 1
  fi
  printf '%s\n' "$content" >"$tmp"
  if ((had_file)); then
    if [[ ! -f "$file" || -L "$file" || "$(cat "$file")" != "$before" ]]; then
      rm "$tmp"
      printf 'install state changed during this run; leaving it untouched: %s\n' "$file" >&2
      return 1
    fi
  elif [[ -e "$file" || -L "$file" ]]; then
    rm "$tmp"
    printf 'install state appeared during this run; leaving it untouched: %s\n' "$file" >&2
    return 1
  fi
  mv "$tmp" "$file"
}

detect_targets() {
  local targets=""
  if command -v claude >/dev/null 2>&1 || [[ -d "$HOME/.claude" ]]; then
    targets=claude
  fi
  if command -v codex >/dev/null 2>&1 || [[ -d "$HOME/.codex" ]]; then
    [[ -z "$targets" ]] || targets+=$'\n'
    targets+=codex
  fi
  if command -v opencode >/dev/null 2>&1 || [[ -d "$HOME/.config/opencode" ]]; then
    [[ -z "$targets" ]] || targets+=$'\n'
    targets+=opencode
  fi
  printf '%s\n' "$targets"
}

while (($#)); do
  arg="$1"
  shift
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
    --check) CHECK_MODE=1 ;;
    --update) UPDATE_MODE=1 ;;
    --git-hook) GIT_HOOK=1 ;;
    --output)
      if (($# == 0)); then
        echo "missing FILE after --output" >&2
        usage >&2
        exit 2
      fi
      CHECK_OUTPUT="$1"
      CHECK_OUTPUT_SET=1
      shift
      ;;
    --output=*)
      CHECK_OUTPUT="${arg#--output=}"
      CHECK_OUTPUT_SET=1
      ;;
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

if [[ "$TARGET" == detected ]] && ((UPDATE_MODE == 0)); then
  RESOLVED_TARGETS="$(detect_targets)"
  if [[ -z "$RESOLVED_TARGETS" ]]; then
    echo "no agent commands or config directories detected; pass --target=claude|codex|opencode|all explicitly" >&2
    usage >&2
    exit 2
  fi
  detected_target_list="${RESOLVED_TARGETS//$'\n'/, }"
  printf 'detected targets: %s\n' "$detected_target_list"
  if [[ "$RESOLVED_TARGETS" == "claude"$'\n'"codex"$'\n'"opencode" ]]; then
    TARGET=all
  elif [[ "$RESOLVED_TARGETS" == *$'\n'* ]]; then
    TARGET=resolved
  else
    TARGET="$RESOLVED_TARGETS"
  fi
fi

if ((UPDATE_MODE)); then
  if [[ -n "$TARGET" || -n "$FILTER_FLAGS" || "$INSTRUCTIONS" == 1 ||
    -n "$GUARDS" || "$UNINSTALL" == 1 || ("$CHECK_OUTPUT_SET" == 1 && "$CHECK_MODE" == 0) ]]; then
    echo "--update replays saved options; do not combine it with target, filter, component, or uninstall options" >&2
    usage >&2
    exit 2
  fi
  if load_install_state; then
    :
  else
    state_status=$?
    exit "$state_status"
  fi
elif [[ -z "$TARGET" ]] && ! ((UNINSTALL && GIT_HOOK)); then
  echo "missing --target=claude|codex|opencode|all|detected" >&2
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

if ((CHECK_MODE)); then
  case "$TARGET" in
    claude | codex | opencode | all) ;;
    resolved)
      if ((UPDATE_MODE)) || [[ -n "$RESOLVED_TARGETS" ]]; then
        :
      else
        echo "invalid --target=$TARGET (expected claude|codex|opencode|all|detected)" >&2
        usage >&2
        exit 2
      fi
      ;;
    *)
      echo "invalid --target=$TARGET (expected claude|codex|opencode|all|detected)" >&2
      usage >&2
      exit 2
      ;;
  esac
  if ((DRY_RUN || UNINSTALL)); then
    echo "--check cannot be combined with --dry-run or --uninstall" >&2
    usage >&2
    exit 2
  fi
  if ((CHECK_OUTPUT_SET)) && [[ -z "${CHECK_OUTPUT//[[:space:]]/}" ]]; then
    echo "invalid empty --output FILE" >&2
    usage >&2
    exit 2
  fi
  DRY_RUN=1
elif ((CHECK_OUTPUT_SET)); then
  echo "--output requires --check" >&2
  usage >&2
  exit 2
fi

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

check_kind_for_what() {
  case "$1" in
    *routed*member*) printf 'routed-member-overrides' ;;
    *"instruction payload"*) printf 'instruction-payload' ;;
    *"instruction"*) printf 'instructions' ;;
    *"Claude rule"*) printf 'claude-rule' ;;
    *"OpenCode agent"*) printf 'opencode-agent' ;;
    *"agent "*) printf 'codex-agent' ;;
    *"PR merge guard"*) printf 'merge-guard' ;;
    *"secret read guard"*) printf 'secret-guard' ;;
    *"legacy"*) printf 'legacy-managed-file' ;;
    *) printf 'managed-file' ;;
  esac
}

check_tsv_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//$'\t'/\\t}"
  value="${value//$'\n'/\\n}"
  printf '%s' "$value"
}

check_record() {
  ((CHECK_MODE)) || return 0
  local target="${1:-$CHECK_CURRENT_TARGET}" kind="$2" path="$3" state="$4" row
  local escaped_target escaped_kind escaped_path escaped_state
  [[ -n "$target" ]] || target="$TARGET"
  escaped_target="$(check_tsv_escape "$target")"
  escaped_kind="$(check_tsv_escape "$kind")"
  escaped_path="$(check_tsv_escape "$path")"
  escaped_state="$(check_tsv_escape "$state")"
  printf -v row '%s\t%s\t%s\t%s' \
    "$escaped_target" "$escaped_kind" "$escaped_path" "$escaped_state"
  [[ $'\n'"$CHECK_ROWS" == *$'\n'"$row"$'\n'* ]] || CHECK_ROWS+="$row"$'\n'
}

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

# Where Claude's earlier symlink installer placed its command skills.
target_command_dir_for() {
  case "$1" in
    claude) printf '%s/.claude/commands\n' "$HOME" ;;
    *)
      echo "unknown target: $1" >&2
      return 1
      ;;
  esac
}

opencode_legacy_command_dir() { printf '%s/.config/opencode/command\n' "$HOME"; }

resolve_targets() {
  if [[ -n "$RESOLVED_TARGETS" ]]; then
    local resolved_target
    while IFS= read -r resolved_target; do
      if [[ -n "$resolved_target" ]]; then
        printf '%s\n' "$resolved_target"
      fi
    done <<<"$RESOLVED_TARGETS"
    return 0
  fi
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
    check_record codex legacy-mcp-runtime "$venv" stale
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

# --- Plugin agent registration ----------------------------------------------
#
# Claude loads plugins/<category>/agents/*.md natively. Codex and OpenCode
# render the same source through scripts/plugin_agents.py into their own formats.
# Generated files carry a marker comment, so install and uninstall never touch
# files we did not generate.

codex_agents_dir() { printf '%s/.codex/agents' "$HOME"; }
opencode_agents_dir() { printf '%s/.config/opencode/agents' "$HOME"; }

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

# Render plugin agent source into the target runtime's format. Both renderers
# share one parser, and both resolve plugin-relative paths for this checkout.
plugin_agent_render() {
  local renderer="$1" md="$2" plugin_dir="$3" marker="$4"
  python3 "$REPO_ROOT/scripts/plugin_agents.py" "$renderer" \
    --source "$md" --plugin-dir "$plugin_dir" --marker "$marker"
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
      if ! toml="$(plugin_agent_render codex "$md" "$REPO_ROOT/plugins/$cat" "$AGENT_MARKER")"; then
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
    check_record codex codex-agent "$dest" stale
    run rm "$dest"
    ((DRY_RUN)) || printf '  removed   %s (agent no longer in repo)\n' "$dest"
  done
}

install_opencode_agents() {
  local agents_dir cats
  agents_dir="$(opencode_agents_dir)"
  cats="$(agent_categories)"
  [[ -n "$cats" ]] || return 0
  if ! command -v python3 >/dev/null 2>&1; then
    printf '  WARN      python3 not found; cannot install OpenCode agents in %s\n' \
      "$agents_dir" >&2
    return 0
  fi
  local cat md name dest markdown
  while IFS= read -r cat; do
    [[ -n "$cat" ]] || continue
    for md in "$REPO_ROOT/plugins/$cat/agents/"*.md; do
      [[ -f "$md" ]] || continue
      name="$(basename "$md" .md)"
      dest="$agents_dir/$name.md"
      if ! markdown="$(plugin_agent_render opencode "$md" "$REPO_ROOT/plugins/$cat" "$AGENT_MARKER")"; then
        printf '  WARN      failed to convert %s for OpenCode (skipping)\n' "$md" >&2
        continue
      fi
      owned_file_set "$dest" opencode-agent <<<"$markdown"
    done
  done <<<"$cats"
}

uninstall_opencode_agents() {
  local agents_dir cat md name dest before
  agents_dir="$(opencode_agents_dir)"
  while IFS= read -r cat; do
    [[ -n "$cat" ]] || continue
    for md in "$REPO_ROOT/plugins/$cat/agents/"*.md; do
      [[ -f "$md" ]] || continue
      name="$(basename "$md" .md)"
      dest="$agents_dir/$name.md"
      [[ -f "$dest" && ! -L "$dest" ]] || continue
      if ! grep -qF "$AGENT_MARKER" "$dest"; then
        printf '  WARN      %s was not generated by us (skipping)\n' "$dest" >&2
        continue
      fi
      before="$(cat "$dest")"
      if ((DRY_RUN)); then
        printf '[dry-run] remove %s\n' "$dest"
        continue
      fi
      if [[ ! -f "$dest" || -L "$dest" || "$(cat "$dest")" != "$before" ]] ||
        ! grep -qF "$AGENT_MARKER" "$dest"; then
        printf '  WARN      %s changed during uninstall (leaving it untouched)\n' "$dest" >&2
        continue
      fi
      rm "$dest"
      printf '  removed   %s\n' "$dest"
    done
  done < <(agent_categories)
}

prune_stale_opencode_agents() {
  local agents_dir dest name before
  agents_dir="$(opencode_agents_dir)"
  [[ -d "$agents_dir" ]] || return 0
  for dest in "$agents_dir"/*.md; do
    [[ -f "$dest" && ! -L "$dest" ]] || continue
    name="$(basename "$dest" .md)"
    compgen -G "$REPO_ROOT/plugins/*/agents/$name.md" >/dev/null && continue
    grep -qF "$AGENT_MARKER" "$dest" || continue
    check_record opencode opencode-agent "$dest" stale
    if ((UPDATE_MODE && CHECK_MODE == 0)); then
      before="$(cat "$dest")"
      if [[ ! -f "$dest" || -L "$dest" || "$(cat "$dest")" != "$before" ]] ||
        ! grep -qF "$AGENT_MARKER" "$dest"; then
        printf '  WARN      %s changed during --update; leaving it untouched\n' "$dest" >&2
        continue
      fi
    fi
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
    check_record claude claude-rule "$1" stale
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
  local file="$HOME/.claude/settings.json" command content before="" existed=0
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
    check_record claude python-init-hook "$file" foreign
    ((CHECK_MODE)) || printf '  WARN      %s is a symlink, leaving it untouched (Python uv-init context hook)\n' \
      "$file" >&2
    return 0
  fi
  if [[ -f "$file" ]]; then
    before="$(cat "$file")"
    existed=1
  fi
  command="$(python_init_hook_command)"
  if ! content="$(claude_settings_with_python_hook "$file" "$command")"; then
    check_record claude python-init-hook "$file" foreign
    ((CHECK_MODE)) || printf '  WARN      %s is not a compatible JSON object, leaving it untouched (Python uv-init context hook)\n' \
      "$file" >&2
    return 0
  fi
  if [[ -f "$file" && "$(cat "$file")" == "$content" ]]; then
    printf '  ok        %s (Python uv-init context hook)\n' "$file"
    return 0
  fi
  if [[ -f "$file" ]]; then
    check_record claude python-init-hook "$file" stale
  else
    check_record claude python-init-hook "$file" missing
  fi
  if ((DRY_RUN)); then
    printf '[dry-run] write %s\n' "$file"
    return 0
  fi
  ensure_parent "${file%/*}"
  if ((UPDATE_MODE)); then
    if ((existed)); then
      if [[ ! -f "$file" || -L "$file" || "$(cat "$file")" != "$before" ]]; then
        printf '  WARN      %s changed during --update; leaving it untouched\n' "$file" >&2
        return 0
      fi
    elif [[ -e "$file" || -L "$file" ]]; then
      printf '  WARN      %s appeared during --update; leaving it untouched\n' "$file" >&2
      return 0
    fi
  fi
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

render_codex_guard_toml() {
  local guard="$1" command
  command="$(guard_command "$guard" codex)"
  python3 - "$REPO_ROOT/scripts" "$(guard_script "$guard")" "$command" <<'PY'
import importlib
import sys

sys.path.insert(0, sys.argv[1])
from pr_merge_guard import codex_hook_toml

guard = importlib.import_module(sys.argv[2])
print(codex_hook_toml(sys.argv[3], guard.HOOK_MATCHER, guard.HOOK_STATUS))
PY
}

codex_guard_trust_findings() {
  local config="$1"
  python3 - "$config" <<'PY'
import ast
import hashlib
import json
import os
import re
import sys

try:
    import tomllib
except ImportError:
    tomllib = None

def toml_scalar(value):
    value = value.strip()
    if value in ("true", "false"):
        return value == "true"
    if re.fullmatch(r"[0-9]+", value):
        return int(value)
    if value.startswith(('"', "'")):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value[1:-1]
    return value

def minimal_toml(text):
    config = {"hooks": {"PreToolUse": [], "state": {}}}
    section = ""
    group = None
    handler = None
    nested_state = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[[hooks.PreToolUse]]":
            group = {"hooks": []}
            config["hooks"]["PreToolUse"].append(group)
            section, handler, nested_state = "group", None, None
            continue
        if line == "[[hooks.PreToolUse.hooks]]":
            if group is None:
                continue
            handler = {}
            group["hooks"].append(handler)
            section, nested_state = "handler", None
            continue
        if line == "[hooks.state]":
            section, group, handler, nested_state = "state", None, None, None
            continue
        if line.startswith("[hooks.state.") and line.endswith("]"):
            key_text = line[len("[hooks.state."):-1]
            nested_state = toml_scalar(key_text)
            config["hooks"]["state"].setdefault(nested_state, {})
            section, group, handler = "nested-state", None, None
            continue
        if line.startswith("[") or "=" not in line:
            section, group, handler, nested_state = "", None, None, None
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if section == "group" and group is not None:
            group[key] = toml_scalar(value)
        elif section == "handler" and handler is not None:
            handler[key] = toml_scalar(value)
        elif section == "state":
            state_key = toml_scalar(key)
            state_entry = {}
            for field in ("trusted_hash", "enabled"):
                match = re.search(rf"\b{field}\s*=\s*([^,}}]+)", value)
                if match:
                    state_entry[field] = toml_scalar(match.group(1))
            config["hooks"]["state"][state_key] = state_entry
        elif section == "nested-state" and nested_state is not None:
            config["hooks"]["state"].setdefault(nested_state, {})[key] = toml_scalar(value)
    return config

try:
    config_path = os.path.abspath(sys.argv[1])
    with open(config_path, "rb") as config_file:
        if tomllib is not None:
            config = tomllib.load(config_file)
        else:
            config = minimal_toml(config_file.read().decode("utf-8"))
except (OSError, UnicodeError, ValueError):
    sys.exit(3)

hooks = config.get("hooks", {})
groups = hooks.get("PreToolUse", []) if isinstance(hooks, dict) else []
state = hooks.get("state", {}) if isinstance(hooks, dict) else {}
if not isinstance(groups, list) or not isinstance(state, dict):
    sys.exit(3)

for guard, filename in (("merge", "pr_merge_guard.py"), ("secret", "secret_read_guard.py")):
    matches = []
    for group_index, group in enumerate(groups):
        if not isinstance(group, dict):
            continue
        handlers = group.get("hooks", [])
        if not isinstance(handlers, list):
            continue
        for handler_index, handler in enumerate(handlers):
            if not isinstance(handler, dict):
                continue
            command = handler.get("command")
            if isinstance(command, str) and filename in command:
                matches.append((group_index, handler_index, group, handler))
    if len(matches) > 1:
        print(f"{guard}\tduplicate")
        continue
    if not matches:
        continue

    group_index, handler_index, group, handler = matches[0]
    normalized = {
        "type": "command",
        "command": handler["command"],
        "timeout": handler.get("timeout", 600),
        "async": handler.get("async", False),
    }
    for field in ("commandWindows", "statusMessage", "additionalContextLimit"):
        if handler.get(field) is not None:
            normalized[field] = handler[field]
    identity = {
        "event_name": "pre_tool_use",
        "matcher": group.get("matcher"),
        "hooks": [normalized],
    }
    current_hash = "sha256:" + hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    keys = (
        f"{config_path}:pre_tool_use:{group_index}:{handler_index}",
        f"{os.path.realpath(config_path)}:pre_tool_use:{group_index}:{handler_index}",
    )
    saved = next((state.get(key) for key in keys if key in state), None)
    if not isinstance(saved, dict) or saved.get("enabled") is False or saved.get("trusted_hash") != current_hash:
        print(f"{guard}\tuntrusted-hook")
PY
}

check_codex_guard_hooks() {
  local config guard begin end marker_count expected actual result status kind
  config="$(codex_config_path)"
  [[ -f "$config" ]] || return 0
  for guard in merge secret; do
    begin="$(guard_begin_marker "$guard")"
    end="$(guard_end_marker "$guard")"
    marker_count="$(grep -Fxc "$begin" "$config" || true)"
    ((marker_count > 0)) || continue
    kind="$(check_kind_for_what "$(guard_label "$guard")")"
    if ! block_markers_balanced "$begin" "$end" <"$config"; then
      check_record codex "$kind" "$config" foreign
      continue
    fi
    if ((marker_count > 1)); then
      check_record codex "$kind" "$config" duplicate
      continue
    fi
    if ! expected="$(render_codex_guard_toml "$guard")"; then
      check_record codex "$kind" "$config" foreign
      continue
    fi
    actual="$(awk -v b="$begin" -v e="$end" '
      $0 == b { inside = 1; next }
      $0 == e { inside = 0; exit }
      inside { if (printed) printf "\n"; printf "%s", $0; printed = 1 }
    ' "$config")"
    [[ "$actual" == "$expected" ]] || check_record codex "$kind" "$config" stale
    result=""
    status=0
    result="$(codex_guard_trust_findings "$config")" || status=$?
    case "$status" in
      0)
        while IFS=$'\t' read -r found_guard state; do
          [[ "$found_guard" == "$guard" ]] || continue
          check_record codex "$kind" "$config" "$state"
        done <<<"$result"
        ;;
      2) check_record codex "$kind" "$config" untrusted-hook ;;
      *) check_record codex "$kind" "$config" foreign ;;
    esac
  done
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
  local file="$HOME/.claude/settings.json" content status=0 before
  [[ -f "$file" ]] && grep -qF pr_merge_guard.py "$file" || return 0
  if ! command -v python3 >/dev/null 2>&1; then
    printf '  WARN      python3 not found; remove the pr_merge_guard.py hook from %s by hand\n' \
      "$file" >&2
    return 0
  fi
  before="$(cat "$file")"
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
    check_record claude merge-guard "$file" stale
    printf '[dry-run] remove %s\n' "$file"
    return 0
  fi
  if ((UPDATE_MODE)) &&
    { [[ ! -f "$file" ]] || [[ -L "$file" ]] || [[ "$(cat "$file")" != "$before" ]] ||
      ! grep -qF pr_merge_guard.py "$file"; }; then
    printf '  WARN      %s changed during --update; leaving it untouched\n' "$file" >&2
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
      if ! toml="$(render_codex_guard_toml "$guard")"; then
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

git_hooks_dir() {
  local git_dir
  if ! git_dir="$(git -C "$REPO_ROOT" rev-parse --absolute-git-dir 2>/dev/null)"; then
    echo "--git-hook requires a Git checkout" >&2
    return 1
  fi
  printf '%s/hooks\n' "$git_dir"
}

render_git_hook() {
  local hook="$1"
  cat <<'HOOK'
#!/bin/sh
# managed-by: fabiandistler/agents install.sh
HOOK
  if [[ "$hook" == post-rewrite ]]; then
    printf '%s\n' 'cat >/dev/null'
  fi
  cat <<'HOOK'
repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 1
cd "$repo_root" || exit 1
if ./install.sh --update --check; then
  exit 0
else
  check_status=$?
  [ "$check_status" -eq 3 ] || exit "$check_status"
fi
exec ./install.sh --update
HOOK
}

git_hook_is_managed() {
  [[ -f "$1" && ! -L "$1" ]] && grep -qxF "$GIT_HOOK_MARKER" "$1"
}

install_git_hooks() {
  local hooks_dir hook file content before
  hooks_dir="$(git_hooks_dir)" || return 1
  ensure_parent "$hooks_dir"
  for hook in post-merge post-rewrite; do
    file="$hooks_dir/$hook"
    content="$(render_git_hook "$hook")"
    if [[ -L "$file" ]] || { [[ -e "$file" ]] && [[ ! -f "$file" ]]; }; then
      printf '  WARN      %s is not a regular hook file (skipping)\n' "$file" >&2
      continue
    fi
    if [[ -f "$file" ]]; then
      before="$(cat "$file")"
      if ! grep -qxF "$GIT_HOOK_MARKER" <<<"$before"; then
        printf '  WARN      %s is not managed by this installer (skipping)\n' "$file" >&2
        continue
      fi
      if [[ "$before" == "$content" && -x "$file" ]]; then
        printf '  ok        %s (Git hook)\n' "$file"
        continue
      fi
      if ((DRY_RUN)); then
        printf '[dry-run] update %s\n' "$file"
        continue
      fi
      write_file_atomic "$file" "$content" "$GIT_HOOK_MARKER" "" "$before" file 755
      printf '  updated   %s (Git hook)\n' "$file"
      continue
    fi
    if ((DRY_RUN)); then
      printf '[dry-run] create %s\n' "$file"
      continue
    fi
    write_file_atomic "$file" "$content" "$GIT_HOOK_MARKER" "" "" file 755
    printf '  created   %s (Git hook)\n' "$file"
  done
}

remove_git_hooks() {
  local hooks_dir hook file before
  hooks_dir="$(git_hooks_dir)" || return 1
  for hook in post-merge post-rewrite; do
    file="$hooks_dir/$hook"
    [[ -e "$file" || -L "$file" ]] || continue
    if ! git_hook_is_managed "$file"; then
      printf '  WARN      %s is not a marker-owned hook (leaving it untouched)\n' "$file" >&2
      continue
    fi
    before="$(cat "$file")"
    if ((DRY_RUN)); then
      printf '[dry-run] remove %s\n' "$file"
      continue
    fi
    if ! git_hook_is_managed "$file" || [[ "$(cat "$file")" != "$before" ]]; then
      printf '  WARN      %s changed during uninstall (leaving it untouched)\n' "$file" >&2
      continue
    fi
    rm "$file"
    printf '  removed   %s (Git hook)\n' "$file"
  done
}

check_git_hooks() {
  local hooks_dir hook file expected actual state
  hooks_dir="$(git_hooks_dir)" || return 1
  for hook in post-merge post-rewrite; do
    file="$hooks_dir/$hook"
    expected="$(render_git_hook "$hook")"
    if [[ -L "$file" ]] || { [[ -e "$file" ]] && [[ ! -f "$file" ]]; }; then
      state=foreign
    elif [[ ! -f "$file" ]]; then
      state=missing
    else
      actual="$(cat "$file")"
      if ! grep -qxF "$GIT_HOOK_MARKER" <<<"$actual"; then
        state=foreign
      elif [[ "$(grep -Fxc "$GIT_HOOK_MARKER" <<<"$actual" || true)" != 1 ]]; then
        state=duplicate
      elif [[ "$actual" != "$expected" || ! -x "$file" ]]; then
        state=stale
      else
        continue
      fi
    fi
    check_record all git-hook "$file" "$state"
  done
}

link_one() {
  local src="$1" dest="$2"
  if [[ -L "$dest" ]]; then
    local current
    current="$(readlink "$dest")"
    if [[ $'\n'"$PLANNED_REBASED_LINKS" == *$'\n'"$dest"$'\n'* ]]; then
      return 0
    fi
    if [[ "$current" == "$src" ]]; then
      printf '  ok        %s -> %s\n' "$dest" "$src"
      return 0
    fi
    if [[ "$current" == "$REPO_ROOT/skills/"* ]]; then
      check_record "$CHECK_CURRENT_TARGET" skill-link "$dest" stale
    else
      check_record "$CHECK_CURRENT_TARGET" skill-link "$dest" foreign
    fi
    ((CHECK_MODE)) || printf '  WARN      %s already symlinked to %s (skipping)\n' "$dest" "$current" >&2
    return 0
  fi
  if [[ -e "$dest" ]]; then
    check_record "$CHECK_CURRENT_TARGET" skill-link "$dest" foreign
    ((CHECK_MODE)) || printf '  WARN      %s exists and is not a symlink (skipping)\n' "$dest" >&2
    return 0
  fi
  check_record "$CHECK_CURRENT_TARGET" skill-link "$dest" missing
  if ((DRY_RUN)); then
    printf '[dry-run] link %s\n' "$dest"
    PLANNED_LINKS+="$dest"$'\n'
    return 0
  fi
  run ln -s "$src" "$dest"
  printf '  linked    %s -> %s\n' "$dest" "$src"
}

PLANNED_REBASED_LINKS=""

rebase_repo_symlink() {
  local link="$1" current suffix new_target
  [[ "$UPDATE_MODE" == 1 && -n "$OLD_REPO_ROOT" && "$OLD_REPO_ROOT" != "$REPO_ROOT" ]] || return 0
  [[ -L "$link" ]] || return 0
  current="$(readlink "$link")"
  [[ "$current" == "$OLD_REPO_ROOT/"* ]] || return 0
  suffix="${current#"$OLD_REPO_ROOT"/}"
  new_target="$REPO_ROOT/$suffix"
  [[ "$new_target" == "$REPO_ROOT/"* && (-e "$new_target" || -L "$new_target") ]] || return 0
  if ((DRY_RUN)); then
    printf '[dry-run] relink %s to current checkout\n' "$link"
    PLANNED_REBASED_LINKS+="$link"$'\n'
    return 0
  fi
  [[ -L "$link" && "$(readlink "$link")" == "$current" ]] || return 0
  rm "$link"
  [[ ! -e "$link" && ! -L "$link" ]] || {
    printf '  WARN      %s changed during --update; leaving it untouched\n' "$link" >&2
    return 0
  }
  [[ -e "$new_target" || -L "$new_target" ]] || return 0
  ln -s "$new_target" "$link"
  printf '  linked    %s -> %s (moved checkout)\n' "$link" "$new_target"
}

rebase_repo_symlink_dir() {
  local dir="$1" link
  [[ -d "$dir" ]] || return 0
  for link in "$dir"/*; do
    [[ -L "$link" ]] || continue
    rebase_repo_symlink "$link"
  done
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
  check_record opencode skill-link "$dest" duplicate
  run rm "$dest"
  ((DRY_RUN)) || printf '  removed   %s (opencode reads it from %s)\n' "$dest" "$root"
}

unlink_one() {
  local src="$1" dest="$2" state="${3:-stale}"
  if [[ ! -L "$dest" ]]; then
    if [[ -e "$dest" ]]; then
      check_record "$CHECK_CURRENT_TARGET" skill-link "$dest" foreign
      ((CHECK_MODE)) || printf '  WARN      %s exists but is not a symlink (skipping)\n' "$dest" >&2
    fi
    return 0
  fi
  local current
  current="$(readlink "$dest")"
  if [[ "$current" != "$src" ]]; then
    check_record "$CHECK_CURRENT_TARGET" skill-link "$dest" foreign
    printf '  WARN      %s points to %s (not ours, skipping)\n' "$dest" "$current" >&2
    return 0
  fi
  check_record "$CHECK_CURRENT_TARGET" skill-link "$dest" "$state"
  if ((DRY_RUN)); then
    printf '[dry-run] remove %s\n' "$dest"
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
    check_record "$CHECK_CURRENT_TARGET" skill-link "$entry" stale
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
    check_record "$CHECK_CURRENT_TARGET" legacy-skill-link "$dest" stale
    run rm "$dest"
    ((DRY_RUN)) || printf '  removed   %s (legacy opencode location)\n' "$dest"
  done <<<"$skills"
}

# Earlier releases linked command skills into OpenCode's singular command/
# directory. Their metadata now exposes the same skill as a slash command from
# skills/, so remove only those old symlinks after the new location is handled.
cleanup_opencode_legacy_commands() {
  local skills="$1" legacy_dir skill source dest
  legacy_dir="$(opencode_legacy_command_dir)"
  [[ -d "$legacy_dir" ]] || return 0
  while IFS= read -r skill; do
    [[ -n "$skill" ]] || continue
    [[ "$(skill_activation "$REPO_ROOT/skills/$skill/SKILL.md")" == command ]] || continue
    source="$REPO_ROOT/skills/$skill/SKILL.md"
    dest="$legacy_dir/$skill.md"
    [[ -L "$dest" ]] || continue
    [[ "$(readlink "$dest")" == "$source" ]] || continue
    check_record opencode "legacy OpenCode command skill" "$dest" stale
    if ((DRY_RUN)); then
      printf '[dry-run] remove %s\n' "$dest"
      continue
    fi
    if [[ ! -L "$dest" || "$(readlink "$dest")" != "$source" ]]; then
      printf '  WARN      %s changed during migration (leaving it untouched)\n' "$dest" >&2
      continue
    fi
    rm "$dest"
    printf '  removed   %s (legacy OpenCode command location)\n' "$dest"
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
    check_record codex legacy-skill-link "$entry" stale
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
      check_record claude legacy-skill-link "$entry" stale
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
    check_record codex legacy-prompt-link "$dest" stale
    run rm "$dest"
    ((DRY_RUN)) || printf '  removed   %s (deprecated codex prompt)\n' "$dest"
  done <<<"$skills"
}

# Link (or, with --uninstall, unlink) the selected skills for one target, then
# prune links to skills the repo no longer ships.
sync_skill_links() {
  local target="$1" skills="$2" routed="$3"
  local dest_dir shared_root
  dest_dir="$(target_dir_for "$target")"
  if ((UNINSTALL == 0)); then
    ensure_parent "$dest_dir"
  fi
  while IFS= read -r skill; do
    local src dest activation category
    activation="$(skill_activation "$REPO_ROOT/skills/$skill/SKILL.md")"
    category="$(skill_category "$REPO_ROOT/skills/$skill/SKILL.md")"
    if [[ "$activation" == "auto" && "$routed" == *" $category "* ]]; then
      # Auto member of a routed category: it is nested under the router's
      # members/ dir and loads lazily when routed to, so it is never linked
      # at top level. Command skills are ordinary skill links for Codex and
      # OpenCode, and their runtime metadata keeps them explicitly invoked.
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
      # A normal auto or command skill, or the router itself (linked as a
      # whole dir so its nested members/ come along).
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
  if [[ "$target" == "opencode" ]]; then
    prune_stale_skill_links "$(opencode_legacy_command_dir)"
  fi
  return 0
}

rebase_managed_repo_paths() {
  local target config guard file agents_dir agent name payloads_dir
  [[ "$UPDATE_MODE" == 1 && "$CHECK_MODE" == 0 && -n "$OLD_REPO_ROOT" &&
    "$OLD_REPO_ROOT" != "$REPO_ROOT" ]] || return 0
  while IFS= read -r target; do
    [[ -n "$target" ]] || continue
    rebase_managed_block_path "$(instruction_file_for "$target")" \
      "$(instructions_begin_marker)" "$(instructions_end_marker)"
    case "$target" in
      claude)
        rebase_repo_symlink_dir "$HOME/.claude/skills"
        rebase_repo_symlink_dir "$HOME/.claude/commands"
        while IFS= read -r file; do
          [[ -n "$file" ]] && rebase_owned_file_path "$file" "$(claude_rule_marker)"
        done < <(list_managed_claude_rules)
        ;;
      codex)
        rebase_repo_symlink_dir "$HOME/.agents/skills"
        rebase_repo_symlink_dir "$HOME/.codex/skills"
        rebase_repo_symlink_dir "$HOME/.codex/prompts"
        config="$(codex_config_path)"
        rebase_managed_block_path "$config" "$(skill_override_begin_marker)" \
          "$(skill_override_end_marker)"
        for guard in merge secret; do
          rebase_managed_block_path "$config" "$(guard_begin_marker "$guard")" \
            "$(guard_end_marker "$guard")"
        done
        agents_dir="$(codex_agents_dir)"
        for agent in "$agents_dir"/*.toml; do
          [[ -f "$agent" ]] || continue
          rebase_owned_file_path "$agent" "$AGENT_MARKER"
        done
        ;;
      opencode)
        rebase_repo_symlink_dir "$HOME/.config/opencode/skills"
        rebase_repo_symlink_dir "$(opencode_legacy_command_dir)"
        rebase_repo_symlink_dir "$HOME/.config/opencode/plugins"
        rebase_repo_symlink_dir "$HOME/.config/opencode/agent"
        agents_dir="$(opencode_agents_dir)"
        for agent in "$agents_dir"/*.md; do
          [[ -f "$agent" && ! -L "$agent" ]] || continue
          rebase_owned_file_path "$agent" "$AGENT_MARKER"
        done
        ;;
    esac
  done < <(resolve_targets)

  payloads_dir="$(instruction_payloads_dir)"
  for name in \
    30-python.md \
    70-code-review-conventions.md \
    80-agent-pipelines.md \
    85-agent-scripts.md; do
    rebase_owned_file_path "$payloads_dir/$name" "$(instruction_payload_marker)"
  done
  rebase_owned_file_path "$payloads_dir/python_init_context.py" \
    '# managed-by: fabiandistler/agents install.sh'
}

main() {
  local skills
  [[ -n "$RESOLVED_TARGETS" ]] || RESOLVED_TARGETS="$(resolve_targets)"
  skills="$(list_skills)"
  if [[ -z "$skills" ]]; then
    echo "no skills found under $REPO_ROOT (env=$ENV, category=$CATEGORY)" >&2
    exit 1
  fi
  rebase_managed_repo_paths
  local routed
  routed="$(routed_categories)"
  [[ "$ENV" != "all" ]] && printf 'env filter: %s\n' "$ENV"
  [[ "$CATEGORY" != "all" ]] && printf 'category filter: %s\n' "$CATEGORY"
  if [[ -n "$FILTER_FLAGS" ]] && target_is_selected claude; then
    printf '  WARN      %s: no effect for claude (its skills come from the plugin marketplace)\n' \
      "${FILTER_FLAGS# }" >&2
  fi

  if ((INSTRUCTIONS && UNINSTALL == 0)); then
    CHECK_CURRENT_TARGET=all
    install_instruction_payloads
  fi

  while IFS= read -r target; do
    [[ -z "$target" ]] && continue
    CHECK_CURRENT_TARGET="$target"
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
        install_codex_member_overrides < <(codex_routed_members "$(target_dir_for codex)" "$skills")
      fi
      ((CHECK_MODE)) && check_codex_guard_hooks
    fi
    if [[ "$target" == "opencode" ]]; then
      cleanup_opencode_legacy "$skills"
      cleanup_opencode_legacy_commands "$skills"
      prune_stale_opencode_agents
      if ((UNINSTALL)); then
        uninstall_opencode_agents
      else
        install_opencode_agents
      fi
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

check_result() {
  local missing=0 stale=0 foreign=0 duplicate=0 untrusted=0
  local target kind path state output_dir tsv
  while IFS=$'\t' read -r target kind path state; do
    case "$state" in
      missing) missing=$((missing + 1)) ;;
      stale) stale=$((stale + 1)) ;;
      foreign) foreign=$((foreign + 1)) ;;
      duplicate) duplicate=$((duplicate + 1)) ;;
      untrusted-hook) untrusted=$((untrusted + 1)) ;;
    esac
  done <<<"$CHECK_ROWS"

  if ((CHECK_OUTPUT_SET)); then
    [[ ! -L "$CHECK_OUTPUT" ]] || {
      echo "--output must not be a symlink: $CHECK_OUTPUT" >&2
      return 1
    }
    [[ ! -d "$CHECK_OUTPUT" ]] || {
      echo "--output must be a file: $CHECK_OUTPUT" >&2
      return 1
    }
    output_dir="${CHECK_OUTPUT%/*}"
    [[ "$output_dir" != "$CHECK_OUTPUT" ]] || output_dir=.
    [[ -d "$output_dir" ]] || {
      echo "--output directory does not exist: $output_dir" >&2
      return 1
    }
    tsv=$'target\tkind\tpath\tstate\n'
    tsv+="$CHECK_ROWS"
    write_file_atomic "$CHECK_OUTPUT" "${tsv%$'\n'}"
  fi

  if [[ -z "$CHECK_ROWS" ]]; then
    printf '%s\n' '--check: clean'
    return 0
  fi
  printf -- '--check: drift (missing=%d stale=%d foreign=%d duplicate=%d untrusted-hook=%d)\n' \
    "$missing" "$stale" "$foreign" "$duplicate" "$untrusted"
  return 3
}

check_main() {
  main >/dev/null
  ((GIT_HOOK)) && check_git_hooks
  check_result
}

if ((CHECK_MODE)); then
  check_main
elif [[ -z "$TARGET" ]] && ((UNINSTALL && GIT_HOOK)); then
  remove_git_hooks
else
  main
  if ((UNINSTALL && GIT_HOOK)); then
    remove_git_hooks
  elif ((GIT_HOOK)); then
    install_git_hooks
  fi
  if ((UNINSTALL == 0 && DRY_RUN == 0)); then
    write_install_state
  fi
fi
