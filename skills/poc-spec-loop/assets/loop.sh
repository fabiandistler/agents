#!/usr/bin/env bash
# poc-spec-loop / Phase 2 driver — SKELETON, not yet run against a real PoC.
#
# Owns everything the per-task prompt must not carry: branch, item selection,
# fresh-context invocation, check execution, attempts/BLOCKED bookkeeping,
# checkpoints, stop conditions, PR.
#
# Preconditions (checked below): POC_AGENT set; origin on a supported forge
# (GitHub, Azure DevOps Services); git, jq, timeout, the forge's CLI (gh, or az
# with the azure-devops extension) and the runner's CLI on PATH; clean tree;
# plans/prd.json with approved:true.
#
# VERIFY BEFORE FIRST RUN: the non-interactive flags of the chosen runner for
# the installed version (`claude --help`, `codex exec --help`,
# `opencode run --help`). Without them headless tool calls are denied and every
# task fails its check. Defaults; codex and opencode flags checked against
# `--help` of codex 0.162.1 and opencode 1.19.0 on 2026-10-12:
#   claude    claude -p <prompt> --allowedTools Bash,Read,Edit,Write,Glob,Grep
#   codex     codex exec --sandbox danger-full-access <prompt>
#             (workspace-write mounts .git read-only on Linux, openai/codex#15505,
#             but each task commits; so: run codex in a container or VM)
#   opencode  opencode run --auto <prompt>
#
# Run logs and last-failure output live under $(git rev-parse --git-dir)/poc-loop,
# never in the working tree, so a stopped run can be restarted as is.

set -euo pipefail
# bash >= 5.2: `&` in a ${var//pat/rep} replacement would expand to the match.
shopt -u patsub_replacement 2>/dev/null || true

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRD=plans/prd.json
SPEC=plans/SPEC.md
BLOCKED=plans/BLOCKED.md
PR_MD=plans/PR.md
CHECKPOINT_EVERY=5
MAX_ATTEMPTS=3
MAX_CONSECUTIVE_BLOCKED=3
MAX_ITEMS=40                        # hard cap from assets/prd.schema.json
AZURE_DESCRIPTION_MAX=3800          # Azure Repos rejects PR descriptions over 4,000 chars
CHECK_TIMEOUT=${CHECK_TIMEOUT:-900} # seconds per check run

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
  cat <<'EOF'
Usage: POC_AGENT=claude|codex|opencode loop.sh [-h|--help]
Env: POC_AGENT=<runner>   required: agent CLI that runs each task and checkpoint.
     POC_AGENT_FLAGS="..." replaces the runner's default flags (space-separated).
     CHECK_TIMEOUT=<s>    per-check timeout in seconds (default 900).
Examples:
  POC_AGENT=codex bash <skill-dir>/assets/loop.sh
  POC_AGENT=claude POC_AGENT_FLAGS="--allowedTools Bash,Read" bash <skill-dir>/assets/loop.sh
Forge: detected from origin's URL: github.com -> gh; dev.azure.com or
     *.visualstudio.com -> az repos (azure-devops extension). Anything else: exit 2.
Exit codes:
  0  success (ready PR, or draft PR when blocked/unreachable items remain)
  2  usage or preconditions failed (bad flag; POC_AGENT missing or unknown; origin not on
     a supported forge; missing tool; dirty tree; prd.json missing or not approved)
  3  blocked stop (3 consecutive blocked items, or prd-01/prd-02 blocked)
EOF
  exit 0
fi
if [[ $# -gt 0 ]]; then
  echo "unknown argument: $1 (see --help)" >&2
  exit 2
fi

# ---------- preconditions ----------
case ${POC_AGENT:-} in
  claude) AGENT_FLAGS=(--allowedTools "Bash,Read,Edit,Write,Glob,Grep") ;;
  codex) AGENT_FLAGS=(--sandbox danger-full-access) ;;
  opencode) AGENT_FLAGS=(--auto) ;;
  *)
    echo "POC_AGENT must be one of: claude, codex, opencode (got: '${POC_AGENT:-}')" >&2
    exit 2
    ;;
esac
[[ -z ${POC_AGENT_FLAGS:-} ]] || read -ra AGENT_FLAGS <<<"$POC_AGENT_FLAGS"
# The configured URL, not `git remote get-url`: that one applies insteadOf rewrites.
origin_url=$(git config --get remote.origin.url || true)
case $origin_url in
  *github.com[:/]*) FORGE=github FORGE_CLI=gh ;;
  *dev.azure.com[:/]* | *.visualstudio.com[:/]*) FORGE=azure FORGE_CLI=az ;;
  *)
    echo "origin must be on github.com or dev.azure.com/*.visualstudio.com (got: '$origin_url')" >&2
    exit 2
    ;;
esac
for bin in git jq "$FORGE_CLI" "$POC_AGENT" timeout; do command -v "$bin" >/dev/null || {
  echo "missing: $bin (timeout: GNU coreutils)" >&2
  exit 2
}; done
if [[ $FORGE == azure ]] && ! az extension show --name azure-devops >/dev/null 2>&1; then
  echo "missing az extension: az extension add --name azure-devops" >&2
  exit 2
fi
[[ -z "$(git status --porcelain)" ]] || {
  echo "working tree not clean" >&2
  exit 2
}
[[ -f $PRD ]] || {
  echo "$PRD missing — run Phase 1" >&2
  exit 2
}
[[ "$(jq -r .approved "$PRD")" == "true" ]] || {
  echo "prd.json not approved" >&2
  exit 2
}
bad_deps=$(jq -r '[.items[].id] as $ids | .items[] | .id as $i | .deps[] | select(. as $d | $ids | index($d) | not) | "\($i) -> \(.)"' "$PRD")
[[ -z $bad_deps ]] || {
  echo "unknown deps in $PRD:"$'\n'"$bad_deps" >&2
  exit 2
}
LOGDIR="$(git rev-parse --absolute-git-dir)/poc-loop"
mkdir -p "$LOGDIR"

# ---------- branch ----------
# .branch is written on the poc branch only, so a restart from main finds the
# existing branch via its ref instead of creating a second one.
BRANCH=$(jq -r '.branch // empty' "$PRD")
[[ -n $BRANCH ]] || BRANCH=$(git for-each-ref --sort=-committerdate --format='%(refname:short)' 'refs/heads/poc/*' | head -n1)
if [[ -z $BRANCH ]]; then
  BRANCH="poc/$(date +%F)"
  git switch -c "$BRANCH" main
  jq --arg b "$BRANCH" '.branch=$b' "$PRD" >"$PRD.tmp" && mv "$PRD.tmp" "$PRD"
  git commit -qam "chore(plans): start loop on $BRANCH"
else
  git switch "$BRANCH"
fi
BASE=$(git merge-base main "$BRANCH")

# ---------- helpers ----------
run_agent() { # one fresh, headless agent context per call
  case $POC_AGENT in
    claude) claude -p "$1" "${AGENT_FLAGS[@]}" ;;
    codex) codex exec "${AGENT_FLAGS[@]}" "$1" ;;
    opencode) opencode run "${AGENT_FLAGS[@]}" "$1" ;;
  esac
}
next_item() { # first item: not passed, attempts<MAX, all deps passed, check != null
  jq -r --argjson m "$MAX_ATTEMPTS" '
    .items as $all
    | [ .items[] | select(.passes==false and .attempts<$m and .check!=null)
        | select( all(.deps[]; . as $d | ($all[] | select(.id==$d) | .passes)) ) ]
    | first // empty | .id' "$PRD"
}
set_field() { jq --arg id "$1" --arg k "$2" --argjson v "$3" \
  '(.items[] | select(.id==$id))[$k]=$v' "$PRD" >"$PRD.tmp" && mv "$PRD.tmp" "$PRD"; }
render_prompt() { # crude template fill; swap for envsubst/jinja if it grows
  local id=$1 tpl
  tpl=$(<"$SKILL_DIR/assets/task-prompt.md")
  local item
  item=$(jq -c --arg id "$id" '.items[]|select(.id==$id)' "$PRD")
  # replacements are quoted: no `&` or backslash in SPEC/check text is special
  tpl=${tpl//\{\{SPEC_MD\}\}/"$(<"$SPEC")"}
  tpl=${tpl//\{\{ID\}\}/"$id"}
  tpl=${tpl//\{\{TITLE\}\}/"$(jq -r .title <<<"$item")"}
  tpl=${tpl//\{\{DETAIL\}\}/"$(jq -r '.detail // ""' <<<"$item")"}
  tpl=${tpl//\{\{CHECK\}\}/"$(jq -r .check <<<"$item")"}
  tpl=${tpl//\{\{ATTEMPT\}\}/"$(($(jq -r .attempts <<<"$item") + 1))"}
  tpl=${tpl//\{\{TOOLCHAINS_MD\}\}/"$SKILL_DIR/references/toolchains.md"}
  local lf="$LOGDIR/last_failure_$id"
  if [[ -s $lf ]]; then
    tpl=${tpl//\{\{LAST_FAILURE\}\}/"$(<"$lf")"}
    tpl=${tpl//\{\{#LAST_FAILURE\}\}/}
    tpl=${tpl//\{\{\/LAST_FAILURE\}\}/}
  else tpl=$(sed '/{{#LAST_FAILURE}}/,/{{\/LAST_FAILURE}}/d' <<<"$tpl"); fi
  printf '%s' "$tpl"
}
discard_uncommitted() { # only committed work counts; nothing leaks into the next task
  git reset -q --hard HEAD && git clean -qfd
}
block_item() {
  local id=$1 reason=$2
  {
    echo "## $id — $(jq -r --arg id "$id" '.items[]|select(.id==$id)|.title' "$PRD")"
    echo
    echo '```'
    echo "$reason"
    echo '```'
    echo
  } >>"$BLOCKED"
  git add "$BLOCKED" "$PRD"
  git commit -qm "chore(plans): block $id"
}
checkpoint() { # every CHECKPOINT_EVERY passed items: code-review since BASE
  local room
  room=$((MAX_ITEMS - $(jq '.items|length' "$PRD")))
  run_agent "Use the code-review skill if available in this session; otherwise review the diff yourself. \
Review changes since $BASE against plans/SPEC.md (Spec) and the repo's lint/test conventions (Standards). \
For each Spec finding, append a new item to plans/prd.json (next free prd-NN id, origin:checkpoint, deps on the causing id, check command, passes:false, attempts:0), \
but at most $room new items (schema cap $MAX_ITEMS); put any further Spec findings into plans/REVIEW.md under 'Spec (over cap)'. \
Write Standards findings to plans/REVIEW.md only. Commit as 'chore(plans): checkpoint findings'." ||
    echo "WARN: checkpoint run failed; continuing without its findings" >&2
  discard_uncommitted
}
unreachable_items() { # open items with a check that were never passed; at end of run: a dep is blocked
  jq -r --argjson m "$MAX_ATTEMPTS" \
    '.items[] | select(.passes==false and .check!=null and .attempts<$m) | "- \(.id) \(.title) (deps: \(.deps|join(", ")))"' "$PRD"
}
pr_body() { # full PR body, committed as plans/PR.md so no forge length limit loses it
  local open_heading=$1 body
  body=$(jq -r '.items[] | "- [\(if .passes then "x" else " " end)] \(.id) \(.title)\(if .manual_reason then " — MANUAL: " + .manual_reason else "" end)"' "$PRD")
  [[ -f $BLOCKED ]] && body+=$'\n\n## Blocked\n'"$(tail -c 8000 "$BLOCKED")"
  [[ -f plans/REVIEW.md ]] && body+=$'\n\n## Standards findings\n'"$(tail -c 8000 plans/REVIEW.md)"
  local unreach
  unreach=$(unreachable_items)
  [[ -n $unreach ]] && body+=$'\n\n## '"$open_heading"$'\n'"$unreach"
  body+=$'\n\n## Deployment\n'"$(awk '/^## Definition of Done/{f=1;next} /^## /{f=0} f' "$SPEC")"
  printf '%s\n' "$body" >"$PR_MD"
  git add "$PR_MD"
  git diff --cached --quiet || git commit -qm "chore(plans): pr body"
}
open_pr() {
  local kind=$1 open_heading=${2:-"Unreachable (a dependency is blocked)"} # draft|ready
  pr_body "$open_heading"
  git push -u origin "$BRANCH"
  local title="PoC loop $BRANCH"
  case $FORGE in
    github) # REST via gh api: GraphQL-backed `gh pr create` is blocked in cloud sessions
      local extra=()
      [[ $kind == draft ]] && extra=(-F draft=true)
      # gh fills {owner}/{repo} from the current repo's git remote; --jq prints the PR URL.
      gh api 'repos/{owner}/{repo}/pulls' --method POST --jq .html_url \
        -f base=main -f head="$BRANCH" -f title="$title" -F body=@"$PR_MD" "${extra[@]}"
      ;;
    azure) # organization and project come from origin via az's --detect default
      local draft=false
      [[ $kind == draft ]] && draft=true
      az repos pr create --source-branch "$BRANCH" --target-branch main --title "$title" \
        --description "$(azure_description)" --draft "$draft"
      ;;
  esac
}
azure_description() { # checklist cut to the cap (bytes >= chars, so it stays under), then a pointer
  awk -v max="$AZURE_DESCRIPTION_MAX" '/^$/{exit} {n+=length($0)+1; if(n>max){print "- …"; exit} print}' "$PR_MD"
  printf '\nFull body (blocked items, findings, deployment): `%s` on branch `%s`.\n' "$PR_MD" "$BRANCH"
}

# ---------- loop ----------
consecutive_blocked=0
passed_since_checkpoint=0
while id=$(next_item) && [[ -n $id ]]; do
  echo "== $id"
  out=$(run_agent "$(render_prompt "$id")" 2>&1 | tee "$LOGDIR/run_$id.log") || true
  discard_uncommitted
  if grep -q '^BLOCKED:' <<<"$out"; then
    set_field "$id" attempts "$MAX_ATTEMPTS"
    block_item "$id" "$(grep '^BLOCKED:' <<<"$out")"
    consecutive_blocked=$((consecutive_blocked + 1))
  elif check_out=$(timeout "$CHECK_TIMEOUT" bash -c "$(jq -r --arg id "$id" '.items[]|select(.id==$id)|.check' "$PRD")" 2>&1); then
    set_field "$id" passes true
    rm -f "$LOGDIR/last_failure_$id"
    git add "$PRD"
    git commit -qm "chore(plans): $id passes"
    consecutive_blocked=0
    passed_since_checkpoint=$((passed_since_checkpoint + 1))
  else
    n=$(($(jq -r --arg id "$id" '.items[]|select(.id==$id)|.attempts' "$PRD") + 1))
    set_field "$id" attempts "$n"
    printf '%s' "$check_out" | tail -c 4000 >"$LOGDIR/last_failure_$id"
    if ((n >= MAX_ATTEMPTS)); then
      block_item "$id" "$check_out"
      consecutive_blocked=$((consecutive_blocked + 1))
    else
      git add "$PRD"
      git commit -qm "chore(plans): $id attempt $n failed"
    fi
  fi
  # stop conditions
  if ((consecutive_blocked >= MAX_CONSECUTIVE_BLOCKED)) || { [[ $id == prd-01 || $id == prd-02 ]] && grep -q "^## $id" "$BLOCKED" 2>/dev/null; }; then
    echo "STOP: blocked run" >&2
    open_pr draft "Not reached (run stopped early)"
    exit 3
  fi
  if ((passed_since_checkpoint >= CHECKPOINT_EVERY)); then
    checkpoint
    passed_since_checkpoint=0
  fi
done

# ---------- end of run ----------
if [[ -n $(unreachable_items) ]] || [[ -s $BLOCKED ]]; then
  echo "END: blocked or unreachable items remain" >&2
  open_pr draft
else
  open_pr ready
fi
