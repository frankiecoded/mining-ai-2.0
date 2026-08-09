#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# AI OS - Hugging Face Space deploy script
#
# Creates/pushes the Space, sets hardware, and loads secrets from hf.secrets.env
#
# Prereqs:
#   pip install -U "huggingface_hub[hf_transfer]"
#   hf auth login            (or set HF_TOKEN)
#   docker                   (only needed to test the image locally)
#
# Usage:
#   1. cp hf.secrets.example.env hf.secrets.env   and fill in your real values
#   2. ./hf_deploy.sh <your-username> <space-name>
# -----------------------------------------------------------------------------
set -euo pipefail

HF_USER="${1:-}"
SPACE_NAME="${2:-aios-worker}"

if [[ -z "$HF_USER" ]]; then
  echo "Usage: $0 <hf-username> <space-name>"
  echo "Example: $0 frank aios-worker"
  exit 1
fi

FULL_ID="$HF_USER/$SPACE_NAME"

if ! command -v hf >/dev/null 2>&1; then
  echo "ERROR: 'hf' CLI not found. Run: pip install -U huggingface_hub && hf auth login"
  exit 1
fi

if [[ ! -f "hf.secrets.env" ]]; then
  echo "ERROR: hf.secrets.env not found. Copy hf.secrets.example.env and fill it in."
  exit 1
fi

echo "==> Ensuring git identity..."
git config user.name  >/dev/null 2>&1 || git config user.name  "$HF_USER"
git config user.email >/dev/null 2>&1 || git config user.email "$HF_USER@users.noreply.huggingface.co"

echo "==> Creating Space (docker SDK)..."
hf spaces create "$FULL_ID" --space-sdk docker --public || true

echo "==> Connecting git remote..."
git init -q
git remote remove origin >/dev/null 2>&1 || true
git remote add origin "https://huggingface.co/spaces/$FULL_ID"
git add -A
git commit -q -m "deploy: AI OS WhatsApp worker" 2>/dev/null || echo "    (nothing new to commit)"
git push origin HEAD:main

echo "==> Setting hardware: CPU Upgrade (always-on, ~\$0.03/hr)..."
hf spaces settings "$FULL_ID" --hardware cpu-upgrade

echo "==> Setting secrets from hf.secrets.env..."
set -a
# shellcheck disable=SC1091
source hf.secrets.env
set +a

# Load space secrets safely (strip comments/blank lines)
while IFS= read -r line; do
  [[ -z "$line" || "$line" == \#* ]] && continue
  KEY="${line%%=*}"
  VAL="${line#*=}"
  hf spaces secrets set "$FULL_ID" "$KEY=$VAL"
  echo "    set $KEY"
done < hf.secrets.env

echo ""
echo "=========================================================="
echo "Deployed: https://huggingface.co/spaces/$FULL_ID"
echo "Build logs: Settings -> Diagnostics on the Space page."
echo "=========================================================="
