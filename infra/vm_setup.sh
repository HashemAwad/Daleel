#!/usr/bin/env bash
# Provision a fresh Ubuntu 24.04 server to run Daleel. Owner: D. Idempotent: safe to re-run.
#
#   on your laptop:  rsync the repo to /opt/daleel on the server (see infra/SETUP.md)
#   NEVER run pytest on the server: the DB tests reload seed tables and delete idle transcripts.
#   on the server:   bash /opt/daleel/infra/vm_setup.sh <public-hostname>
#                    e.g. 13-51-237-14.sslip.io  (gives a real HTTPS certificate with no domain)
#
# Brings up: Postgres (docker), the app (uvicorn channels.asgi:app), the retention loop,
# Ollama with a small local model, and Caddy for HTTPS. The DB is never published publicly.
set -euo pipefail

HOST="${1:?usage: vm_setup.sh <public-hostname>}"
APP=/opt/daleel
MODEL="${DALEEL_MODEL:-qwen3:4b}"
cd "$APP"

echo "== swap (the models are tight in 8 GB)"
if ! sudo swapon --show | grep -q /swapfile; then
  sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "== packages"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io docker-compose-v2 python3-venv python3-pip build-essential python3-dev caddy curl >/dev/null

echo "== .env"
umask 077
if [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s|^SESSION_HASH_SALT=.*|SESSION_HASH_SALT=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')|" .env
  sed -i "s|^DALEEL_LOCAL_MODEL=.*|DALEEL_LOCAL_MODEL=$MODEL|" .env
  sed -i "s|^STORE_TRANSCRIPT_TEXT=.*|STORE_TRANSCRIPT_TEXT=1|; s|^RETENTION_IDLE_MINUTES=.*|RETENTION_IDLE_MINUTES=2|; s|^RETENTION_INTERVAL_SECONDS=.*|RETENTION_INTERVAL_SECONDS=20|" .env
fi
chmod 600 .env
sed -i "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=https://$HOST|" .env
# Internet-facing: webhooks must be signed (they fail closed until the Twilio / Meta secrets are set),
# and the test suite must refuse to run against this database.
for kv in DALEEL_ENV=production REQUIRE_TWILIO_SIGNATURE=true REQUIRE_META_SIGNATURE=true; do
  grep -q "^${kv%%=*}=" .env || echo "$kv" >> .env
done

echo "== database"
sudo docker compose up -d
db_ok=no
for _ in $(seq 1 30); do
  if [ "$(sudo docker inspect -f '{{.State.Health.Status}}' "$(sudo docker compose ps -q db)" 2>/dev/null)" = healthy ]; then db_ok=yes; break; fi
  sleep 2
done
[ "$db_ok" = yes ] || { echo "FAILED: database did not become healthy in 60s"; exit 1; }

echo "== python packages (CPU-only torch keeps the download small)"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/pip install -q torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -q -r src/ai/requirements-ai.txt     # must succeed: without it the app serves stub answers

echo "== schema + seed data"
PYTHONPATH=src .venv/bin/python -m data.db
PYTHONPATH=src .venv/bin/python -m data.loaders

echo "== local model"
command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh >/dev/null
ollama pull "$MODEL" >/dev/null

echo "== services"
unit() {  # name, description, command
  sudo tee "/etc/systemd/system/$1.service" >/dev/null <<EOF
[Unit]
Description=$2
After=network-online.target docker.service
[Service]
User=$USER
WorkingDirectory=$APP
Environment=PYTHONPATH=src
ExecStart=$3
Restart=always
RestartSec=3
NoNewPrivileges=yes
PrivateTmp=yes
[Install]
WantedBy=multi-user.target
EOF
}
unit daleel-app "Daleel app" "$APP/.venv/bin/uvicorn channels.asgi:app --host 127.0.0.1 --port 8000"
unit daleel-retention "Daleel transcript retention loop" "$APP/.venv/bin/python -m data.retention --loop"
printf '%s {\n\trequest_body {\n\t\tmax_size 64KB\n\t}\n\treverse_proxy 127.0.0.1:8000\n}\n' "$HOST" | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable -q daleel-app daleel-retention caddy
sudo systemctl restart daleel-app daleel-retention caddy

echo "== check"
for _ in $(seq 1 30); do curl -fsS -m 3 http://127.0.0.1:8000/health >/dev/null 2>&1 && break; sleep 2; done
curl -fsS -m 5 http://127.0.0.1:8000/health && echo
# /health is always ok. A failed import silently swaps in a stub that returns FAKE answers, so check for that.
providers=$(curl -fsS -m 10 http://127.0.0.1:8000/health/channels)
if echo "$providers" | grep -q '"Stub'; then
  echo "FAILED: a stub provider is live (fake answers). Providers: $providers"; exit 1
fi
echo "public URL:      https://$HOST"
echo "Twilio webhook:  https://$HOST/webhook/whatsapp   (POST)"
echo "join page:       https://$HOST/join"
