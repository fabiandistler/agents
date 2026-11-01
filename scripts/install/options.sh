# shellcheck shell=bash
# Sourced by install.sh. Parse and validate the command line; sets the option globals or exits 2.

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
elif ((UNINSTALL == 0)) && [[ -f "$(install_state_file)" ]]; then
  # A plain install overwrites the saved repo root, so it must rebase links
  # from a moved checkout now; a later --update would see equal roots.
  OLD_REPO_ROOT="$(load_install_state >/dev/null && printf '%s' "$OLD_REPO_ROOT")"
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
