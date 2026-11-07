#!/usr/bin/env bash
# check-file-tokens.sh - pre-commit hook: blocks staged text files over 5000
# tokens (tokens = bytes / 4), so no file outgrows what an agent reads in one
# go. Files no agent writes by hand are skipped: lockfiles and minified
# bundles by name, generated or vendored files by their .gitattributes
# (linguist-generated, linguist-vendored) or by a generator banner
# ("@generated", "DO NOT EDIT") in their first five lines.
#
# bats-exempt: hook, copied into target repos by setup-hooks.sh; its tests are
# test/check-file-tokens.bats in the repo-maintenance plugin repo.
#
# Invocation and exit codes: usage() below, or --help.

set -euo pipefail

MAX_TOKENS=5000
BYTES_PER_TOKEN=4
# Split parts aim below the limit so the next edit does not push a freshly
# split file straight back over it.
PART_TOKENS=4000

usage() {
  cat <<'EOF'
Usage: check-file-tokens.sh FILE...
Fails when a FILE is over 5000 tokens (tokens = bytes / 4, so over 20000
bytes) and prints how to split it. prek passes the staged text files.
Lockfiles, minified bundles, files marked linguist-generated or
linguist-vendored in .gitattributes, and files with "@generated" or
"DO NOT EDIT" in their first five lines are skipped.
Exit codes:
  0  every FILE is within the limit or skipped
  1  at least one FILE is over the limit (a finding: the commit is blocked)
Plugin-wide exit code table: "## Exit codes" in plugins/repo-maintenance/README.md
(repo fabiandistler/repo-maintenance).
EOF
}

case "${1:-}" in
  -h | --help)
    usage
    exit 0
    ;;
esac

# not_agent_authored FILE - true for files a tool writes, not a person or agent.
not_agent_authored() {
  local file="$1"
  case "$(basename -- "$file")" in
    *.lock | *.lockfile | package-lock.json | npm-shrinkwrap.json | pnpm-lock.yaml | \
      go.sum | packages.lock.json | *.min.js | *.min.css | *.map)
      return 0
      ;;
  esac
  # Here-strings, not pipes: grep -q exits on the first match, and under
  # pipefail the writer's SIGPIPE would turn a match into a miss.
  local attrs banner
  attrs="$(git check-attr linguist-generated linguist-vendored -- "$file")"
  grep -qE ': (set|true)$' <<<"$attrs" && return 0
  banner="$(head -n 5 -- "$file")"
  grep -qiE '@generated|do not edit' <<<"$banner"
}

max_bytes=$((MAX_TOKENS * BYTES_PER_TOKEN))
part_bytes=$((PART_TOKENS * BYTES_PER_TOKEN))
oversized=()
for file in "$@"; do
  bytes=$(($(wc -c <"$file")))
  if ((bytes > max_bytes)) && ! not_agent_authored "$file"; then
    tokens=$(((bytes + BYTES_PER_TOKEN - 1) / BYTES_PER_TOKEN))
    parts=$(((bytes + part_bytes - 1) / part_bytes))
    oversized+=("  ${file}: ${tokens} tokens, split it into at least ${parts} files")
  fi
done

((${#oversized[@]} == 0)) && exit 0

{
  echo "Files over the ${MAX_TOKENS}-token limit (tokens = bytes / ${BYTES_PER_TOKEN}, so over ${max_bytes} bytes):"
  printf '%s\n' "${oversized[@]}"
  cat <<EOF

Files stay under ${MAX_TOKENS} tokens so an agent can read any file whole
without crowding out the rest of its context.

How to split a file:
  1. Find the seams. Group the content by what it is about: one concept,
     data format or audience per file. Do not cut by line count, and do
     not name pieces part1/part2.
  2. Move each group into its own file of at most ${PART_TOKENS} tokens (${part_bytes}
     bytes), named for what it holds (config_parser.py, not utils2.py).
     The headroom keeps the next edit from hitting the limit again.
  3. Reconnect the pieces so nothing is lost:
     - Code: move cohesive functions or classes into a new module and
       import it where they are used (Python: import; R: a new file under
       R/ in a package, else source(); shell: source). Move their tests
       with them.
     - Markdown (README, AGENTS.md, SKILL.md, docs): keep an overview with
       a short paragraph per topic, move each long section into its own
       file (docs/<topic>.md, references/<topic>.md) and link it.
     - Tests: one test file per module or behaviour under test.
     - Data and fixtures: one file per case.
  4. Verify: run the tests, check that every import, source() and link
     resolves, git add the new files, and commit again.

Generated or vendored? Lockfiles, minified bundles and files with
"@generated" or "DO NOT EDIT" in their first five lines are skipped. Mark
any other file no one edits by hand in .gitattributes instead of splitting:
  path/to/file linguist-generated
Do not bypass this check with git commit --no-verify.
EOF
} >&2
exit 1
