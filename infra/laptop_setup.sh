#!/usr/bin/env bash
# Set up a laptop (macOS or Linux) to host the Daleel demo. Owner: D. Idempotent: safe to re-run.
#
#   install first:  Docker Desktop (or OrbStack), Ollama (https://ollama.com), Python 3.12
#   then:           bash infra/laptop_setup.sh
#   then:           bash infra/run_demo.sh          (see infra/SETUP.md for the public URL)
#
# It never overwrites an existing .env. NEVER run pytest on the demo laptop afterwards:
# the DB tests reload seed tables and delete transcripts (DALEEL_ENV=production makes them refuse).
set -euo pipefail
cd "$(dirname "$0")/.."
fail() { echo "FAILED: $*"; exit 1; }

echo "== tools"
PY=""
for p in python3.12 python3.13 python3.11 python3.10 python3; do
  if command -v "$p" >/dev/null && "$p" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then PY="$p"; break; fi
done
[ -n "$PY" ] || fail "need Python 3.10 or newer (macOS: brew install python@3.12)"
docker info >/dev/null 2>&1 || fail "Docker is not running: start Docker Desktop / OrbStack"
command -v ollama >/dev/null || fail "Ollama is not installed: https://ollama.com"
ollama list >/dev/null 2>&1 || fail "Ollama is not running: open the Ollama app (or run: ollama serve)"

echo "== .env"
if [ ! -f .env ]; then
  # python, not sed -i: BSD sed on macOS takes different arguments
  "$PY" - <<'EOF'
import re, secrets
demo = {"SESSION_HASH_SALT": secrets.token_urlsafe(32), "STORE_TRANSCRIPT_TEXT": "1",
        "RETENTION_IDLE_MINUTES": "2", "RETENTION_INTERVAL_SECONDS": "20",
        "REQUIRE_TWILIO_SIGNATURE": "true", "DALEEL_ENV": "production"}
text = open(".env.example").read()
for key, value in demo.items():
    text, n = re.subn(rf"(?m)^{key}=\S*", f"{key}={value}", text)
    assert n == 1, key
open(".env", "w").write(text)
EOF
  echo "created .env with demo settings (Twilio values and PUBLIC_BASE_URL still empty)"
fi
chmod 600 .env
MODEL=$(sed -n 's/^DALEEL_MODEL=\([^ #]*\).*/\1/p' .env)
[ -n "$MODEL" ] || fail "DALEEL_MODEL is not set in .env"

echo "== database"
docker compose up -d
db_ok=no
for _ in $(seq 1 30); do
  if [ "$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q db)" 2>/dev/null)" = healthy ]; then db_ok=yes; break; fi
  sleep 2
done
[ "$db_ok" = yes ] || fail "database did not become healthy in 60s"

echo "== python packages (the first run downloads about 2 GB)"
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
if ! .venv/bin/pip install -q -r src/ai/requirements-ai.txt 2>/dev/null; then
  # Newest Pythons: camel-tools' editdistance dependency has no wheel. We only use camel_tools.utils, which does not need it.
  { grep -v '^camel-tools' src/ai/requirements-ai.txt | .venv/bin/pip install -q -r /dev/stdin \
      && .venv/bin/pip install -q --no-deps camel-tools emoji; } \
    || fail "AI packages did not install (try Python 3.12); without them the app serves stub answers"
fi

echo "== schema + seed data"
PYTHONPATH=src .venv/bin/python -m data.db
PYTHONPATH=src .venv/bin/python -m data.loaders

echo "== local model ($MODEL)"
ollama list | awk 'NR > 1 {print $1}' | grep -qx "$MODEL" || ollama pull "$MODEL"

echo "== voice + search models (about 2.7 GB the first time; otherwise the first voice note downloads them on stage)"
PYTHONPATH=src .venv/bin/python - <<'EOF' || echo "WARNING: a model did not download; re-run this script on a better connection"
from ai.ingest import EMBED_MODEL
from ai.transcribe import TranscriberImpl
from sentence_transformers import SentenceTransformer
TranscriberImpl()._load()
SentenceTransformer(EMBED_MODEL)
EOF

echo "== check"
# A failed import silently swaps in a stub that returns FAKE answers, so check for that.
PYTHONPATH=src .venv/bin/python - <<'EOF' || fail "a stub provider is live (fake answers); fix the import above"
import sys
from core import providers
from data.db import get_conn
names = {n: type(getattr(providers, n)).__name__ for n in ("llm", "procedures", "directory", "medicine", "transcriber")}
print("providers:", names)
with get_conn() as conn:
    for table in ("drugs", "facilities", "hotlines", "procedures"):
        print(f"{table}: {conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n']} rows")
sys.exit(any(v.startswith("Stub") for v in names.values()))
EOF
echo "ready. next: bash infra/run_demo.sh   (procedures: 0 rows means B's ingestion has not been run here)"
