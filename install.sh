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
# Claude gets skills, command skills and subagents from the plugin marketplace
# only (claude plugin marketplace add fabiandistler/agents, then claude plugin
# install <category>@fabiandistler-agents). --target=claude therefore only syncs
# --instructions and the guard plugins (--merge-guard, --secret-guard; see
# below), and every claude run (install or uninstall) removes what earlier
# versions created: our links in ~/.claude/skills and ~/.claude/commands and
# the merge-guard entry in ~/.claude/settings.json.
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
# the merge-guard plugin, installed with the claude CLI, which first adds the
# marketplace if Claude lacks it (a plugin the user disabled stays disabled).
# --merge-guard --uninstall removes exactly these, leaving other settings and
# hooks alone.
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
# They act only in the installing checkout, not in its linked worktrees, and
# --git-hook exits 1 without writing while core.hooksPath is set.
# --target=detected selects agents with an installed command or config directory.
# --uninstall keeps that state in step: removing the whole saved selection
# deletes the file, removing whole targets or categories rewrites it without
# them, and --dry-run prints which of the two it would do. A category or env
# removed from only some saved targets cannot be recorded; the state then stays
# as it was and the run says so on stderr.
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
# Saved install state, filled by read_install_state.
SAVED_TARGETS_CSV=""
SAVED_ENV=""
SAVED_CATEGORY=""
SAVED_INSTRUCTIONS=0
SAVED_MERGE=0
SAVED_SECRET=0
SAVED_REPO_ROOT=""
# What --uninstall does to the saved state, filled by plan_uninstall_state.
UNINSTALL_STATE_ACTION=keep
UNINSTALL_STATE_BEFORE=""
UNINSTALL_STATE_TARGETS=""
UNINSTALL_STATE_CATEGORY=""
UNINSTALL_STATE_INSTRUCTIONS=0
UNINSTALL_STATE_MERGE=0
UNINSTALL_STATE_READ_GUARD=0
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
  --target=AGENT               Agent to install into or uninstall from
  --env=coding|chat|all        Filter skills (default: all)
  --category=NAME[,NAME...]    Filter skill categories
  --instructions               Install shared instruction rules
  --merge-guard                Install the PR merge guard
  --secret-guard               Install the secret read guard
  --dry-run                    Preview changes without writing
  --uninstall                  Remove selected files and drop them from
                               the saved install
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

# shellcheck source=scripts/install/state.sh
source "$REPO_ROOT/scripts/install/state.sh"

# shellcheck source=scripts/install/options.sh
source "$REPO_ROOT/scripts/install/options.sh"

# shellcheck source=scripts/install/selection.sh
source "$REPO_ROOT/scripts/install/selection.sh"

# shellcheck source=scripts/install/managed-blocks.sh
source "$REPO_ROOT/scripts/install/managed-blocks.sh"

# shellcheck source=scripts/install/codex-config.sh
source "$REPO_ROOT/scripts/install/codex-config.sh"

# shellcheck source=scripts/install/plugin-agents.sh
source "$REPO_ROOT/scripts/install/plugin-agents.sh"

# shellcheck source=scripts/install/instructions.sh
source "$REPO_ROOT/scripts/install/instructions.sh"

# shellcheck source=scripts/install/claude-rules.sh
source "$REPO_ROOT/scripts/install/claude-rules.sh"

# shellcheck source=scripts/install/guards.sh
source "$REPO_ROOT/scripts/install/guards.sh"

# shellcheck source=scripts/install/links.sh
source "$REPO_ROOT/scripts/install/links.sh"

# shellcheck source=scripts/install/skill-links.sh
source "$REPO_ROOT/scripts/install/skill-links.sh"

# shellcheck source=scripts/install/main.sh
source "$REPO_ROOT/scripts/install/main.sh"

# Resolve the hooks dir before main so a refused --git-hook leaves no partial install.
if ((GIT_HOOK)); then
  git_hooks_dir >/dev/null || exit 1
fi

if ((CHECK_MODE)); then
  check_main
elif [[ -z "$TARGET" ]] && ((UNINSTALL && GIT_HOOK)); then
  remove_git_hooks
else
  if ((UNINSTALL)); then
    plan_uninstall_state
  fi
  main
  if ((UNINSTALL && GIT_HOOK)); then
    remove_git_hooks
  elif ((GIT_HOOK)); then
    install_git_hooks
  fi
  if ((UNINSTALL)); then
    apply_uninstall_state
  elif ((DRY_RUN == 0)); then
    write_install_state "$(resolve_targets | paste -sd, -)" "$ENV" "$CATEGORY" "$INSTRUCTIONS" \
      "$([[ "$GUARDS" == *' merge'* ]] && printf 1 || printf 0)" \
      "$([[ "$GUARDS" == *' secret'* ]] && printf 1 || printf 0)" "$REPO_ROOT"
  fi
fi
