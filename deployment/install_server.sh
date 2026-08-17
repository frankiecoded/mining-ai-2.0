#!/usr/bin/env bash
#
# One-shot server install for AI Mining OS.
# Deploys the codebase, Python environment, systemd backend service and the
# Cloudflare tunnel to a fresh Linux server.
#
# Usage (run ON the server, in the project copy):
#   sudo bash deployment/install_server.sh --app-dir /opt/mine-ai
#
set -euo pipefail

APP_DIR="/opt/mine-ai"
SERVICE_USER="aios"

log()  { printf '\033[1;36m[server-install]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[server-install]\033[0m %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --app-dir) APP_DIR="${2:-}"; shift 2 ;;
        --user)    SERVICE_USER="${2:-}"; shift 2 ;;
        *) die "Unknown argument: $1" ;;
    esac
done

[[ "$(id -u)" -eq 0 ]] || die "Run with sudo."

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
log "Installing AI Mining OS from $SRC_DIR to $APP_DIR"

# 1. System packages
log "Installing system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip curl git || true

# 2. Copy the application (exclude git/node_modules/venv)
log "Copying application files..."
mkdir -p "$APP_DIR"
rsync -a --exclude '.git' --exclude '.venv' --exclude 'node_modules' \
      --exclude 'frontend/dist' --exclude '__pycache__' --exclude '.pytest_cache' \
      "$SRC_DIR"/ "$APP_DIR"/

# 3. Service user (if not already present)
if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
    log "Creating service user '$SERVICE_USER'..."
    useradd --system --create-home --shell /usr/sbin/nologin "$SERVICE_USER" || true
fi

# 4. Python environment
log "Creating virtual environment..."
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

# 5. Environment file
if [[ ! -f "$APP_DIR/.env" ]]; then
    log "Creating .env from example (EDIT $APP_DIR/.env with your API_KEY/SECRET_KEY)..."
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
fi
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR/storage" 2>/dev/null || true

# 6. Backend systemd service
log "Installing aios-api.service..."
sed -e "s|^WorkingDirectory=.*|WorkingDirectory=${APP_DIR}|" \
    -e "s|^EnvironmentFile=.*|EnvironmentFile=${APP_DIR}/.env|" \
    -e "s|^ExecStart=.*|ExecStart=${APP_DIR}/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000|" \
    -e "s|^User=.*|User=${SERVICE_USER}|" \
    -e "s|^Group=.*|Group=${SERVICE_USER}|" \
    -e "s|^ReadWritePaths=.*|ReadWritePaths=${APP_DIR}/storage|" \
    "$SRC_DIR/deployment/aios-api.service" > /etc/systemd/system/aios-api.service
systemctl daemon-reload
systemctl enable aios-api

log "Install complete."
log "Next:"
log "  1. sudo nano $APP_DIR/.env        # set API_KEY, SECRET_KEY, CORS_ORIGINS"
log "  2. sudo systemctl start aios-api  # start the backend"
log "  3. bash $APP_DIR/deployment/cloudflared_setup.sh --domain your-domain.com"
