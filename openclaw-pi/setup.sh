#!/usr/bin/env bash
# OpenClaw on Raspberry Pi 4 — bootstrap.
# Idempotent. Re-run any time; it skips finished steps.
#
# Usage on the Pi (as your normal user, NOT root):
#   bash openclaw-pi/setup.sh
#
# What it does:
#   1. Sanity-checks Pi OS Lite 64-bit + arch
#   2. Updates apt, installs base packages, enables unattended-upgrades
#   3. Adds 2 GB swap if missing, sets vm.swappiness=10
#   4. Installs Node.js 24 from NodeSource
#   5. Installs Claude Code CLI + OpenClaw globally
#   6. Pauses for browser-based Claude Max OAuth login
#   7. Stages openclaw.json from the example, deploys systemd drop-in
#   8. Runs `openclaw onboard --install-daemon` (you pick "Claude CLI")
#   9. Tells you how to grab your Telegram numeric ID and finalize config

set -Eeuo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENCLAW_HOME="${HOME}/.openclaw"
SECRETS_DIR="${OPENCLAW_HOME}/secrets"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user/openclaw.service.d"

log()   { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }
warn()  { printf '\n\033[1;33m!! \033[0m %s\n' "$*" >&2; }
fail()  { printf '\n\033[1;31mxx \033[0m %s\n' "$*" >&2; exit 1; }
pause() { printf '\n\033[1;35m?? \033[0m %s\n   Press ENTER to continue, Ctrl-C to abort. ' "$*"; read -r _; }

require_user() {
  [[ $EUID -ne 0 ]] || fail "Run as your regular user, not root. (sudo is invoked per command.)"
  command -v sudo >/dev/null || fail "sudo is required."
}

check_arch() {
  local arch; arch="$(uname -m)"
  [[ "$arch" == "aarch64" ]] || fail "Need 64-bit ARM (aarch64). Found: $arch. Reflash with Raspberry Pi OS Lite 64-bit."
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    log "OS: ${PRETTY_NAME:-unknown} ($arch)"
  fi
}

apt_base() {
  log "Updating apt and installing base packages"
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get -y -qq full-upgrade
  sudo DEBIAN_FRONTEND=noninteractive apt-get -y -qq install \
    curl git ca-certificates gnupg jq unattended-upgrades

  log "Enabling unattended-upgrades for security patches"
  sudo dpkg-reconfigure -f noninteractive unattended-upgrades >/dev/null
}

setup_swap() {
  if swapon --show | grep -q '/swapfile'; then
    log "Swap already active — skipping"
  else
    log "Creating 2 GB swapfile"
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile >/dev/null
    sudo swapon /swapfile
    grep -q '^/swapfile ' /etc/fstab || \
      echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
  fi
  if ! grep -q '^vm.swappiness' /etc/sysctl.conf; then
    echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf >/dev/null
    sudo sysctl -p >/dev/null
  fi
}

install_node() {
  if command -v node >/dev/null && node -v | grep -qE '^v(2[4-9]|[3-9][0-9])\.'; then
    log "Node $(node -v) already installed — skipping"
    return
  fi
  log "Installing Node.js 24 from NodeSource"
  curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
  sudo DEBIAN_FRONTEND=noninteractive apt-get -y -qq install nodejs
  log "Node $(node -v), npm $(npm -v)"
}

install_npm_globals() {
  log "Configuring npm global prefix to ~/.npm-global (no sudo for global installs)"
  mkdir -p "${HOME}/.npm-global"
  npm config set prefix "${HOME}/.npm-global"
  case ":$PATH:" in
    *":${HOME}/.npm-global/bin:"*) : ;;
    *)
      if ! grep -q 'npm-global/bin' "${HOME}/.bashrc" 2>/dev/null; then
        echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> "${HOME}/.bashrc"
      fi
      export PATH="${HOME}/.npm-global/bin:${PATH}"
      ;;
  esac

  log "Installing Claude Code CLI"
  npm install -g @anthropic-ai/claude-code

  log "Installing OpenClaw"
  npm install -g openclaw@latest

  log "Versions: claude=$(claude --version 2>/dev/null || echo '?'), openclaw=$(openclaw --version 2>/dev/null || echo '?')"
}

claude_max_login() {
  if [[ -d "${HOME}/.claude" ]] && claude --version >/dev/null 2>&1; then
    log "~/.claude exists — assuming you're logged in. Re-run 'claude /login' if not."
    return
  fi
  cat <<'EOF'

============================================================
 NEXT STEP — Claude Max login (one time, in a browser)
============================================================
We'll launch the Claude Code CLI now. It will print a URL.
Open the URL on any device, sign in with the Anthropic account
that holds your Claude Max subscription, and approve.

OpenClaw will reuse this login automatically — no API keys, the
inference runs on your Max plan.

When the login is finished, type /exit in the Claude prompt to
return to this script.
============================================================

EOF
  pause "Ready to launch 'claude'?"
  claude || true
}

stage_config() {
  mkdir -p "${OPENCLAW_HOME}" "${SECRETS_DIR}"
  chmod 700 "${OPENCLAW_HOME}" "${SECRETS_DIR}"

  if [[ ! -f "${OPENCLAW_HOME}/openclaw.json" ]]; then
    log "Staging openclaw.json from example (you'll fill in your Telegram ID later)"
    cp "${REPO_DIR}/openclaw.json.example" "${OPENCLAW_HOME}/openclaw.json"
  else
    log "${OPENCLAW_HOME}/openclaw.json already exists — leaving it alone"
  fi

  if [[ ! -f "${SECRETS_DIR}/telegram-token" ]]; then
    log "Staging telegram-token placeholder. Edit it after running BotFather."
    cp "${REPO_DIR}/secrets/telegram-token.example" "${SECRETS_DIR}/telegram-token"
    chmod 600 "${SECRETS_DIR}/telegram-token"
  fi
}

install_systemd_dropin() {
  log "Installing systemd user service drop-in for hardening + auto-restart"
  mkdir -p "${SYSTEMD_USER_DIR}"
  cp "${REPO_DIR}/systemd/openclaw.service.d/override.conf" "${SYSTEMD_USER_DIR}/override.conf"
  loginctl enable-linger "$USER" >/dev/null 2>&1 || sudo loginctl enable-linger "$USER"
}

run_onboard() {
  cat <<'EOF'

============================================================
 NEXT STEP — `openclaw onboard --install-daemon`
============================================================
The wizard will ask for a provider. Choose:

   >>> Claude CLI <<<

OpenClaw will detect your existing Claude Max login.
If it asks about channels, you can skip — we already have
Telegram in the staged openclaw.json (set the bot token next).
============================================================

EOF
  pause "Ready to run onboard?"
  openclaw onboard --install-daemon || warn "Onboard exited non-zero — review and re-run if needed."

  systemctl --user daemon-reload || true
  systemctl --user restart openclaw 2>/dev/null || systemctl --user start openclaw 2>/dev/null || true
}

final_hints() {
  cat <<EOF

============================================================
 Done. Final manual steps (see README for details):
============================================================

 1. Telegram bot:
      • Open Telegram, message @BotFather, /newbot
      • Paste the token (just the token, no quotes) into:
          ${SECRETS_DIR}/telegram-token
      • chmod 600 was already set

 2. Find your numeric Telegram user ID:
      • Send any DM to your new bot
      • Run: openclaw logs --follow
      • Look for "from": { "id": <NUMBER> }
      • Copy that number

 3. Edit ~/.openclaw/openclaw.json:
      • Replace every <DEINE_TELEGRAM_ID> with the number above
      • Save

 4. Restart and verify:
      systemctl --user restart openclaw
      openclaw doctor
      openclaw models list --provider anthropic

 5. DM the bot — it should reply.

If anything looks off, run \`openclaw doctor\` first.
EOF
}

main() {
  require_user
  check_arch
  apt_base
  setup_swap
  install_node
  install_npm_globals
  claude_max_login
  stage_config
  install_systemd_dropin
  run_onboard
  final_hints
}

main "$@"
