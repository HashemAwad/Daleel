#!/usr/bin/env bash
# Run the demo on a laptop: the app on 127.0.0.1:8000 plus the retention loop. Owner: D.
# Ctrl-C stops both. Run infra/laptop_setup.sh once first; the tunnel runs in its own terminal.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src
trap 'kill 0' EXIT
if command -v caffeinate >/dev/null; then caffeinate -dims -w $$ & fi    # macOS: stay awake while this runs
.venv/bin/python -m data.retention --loop &       # without it nothing is ever deleted
.venv/bin/uvicorn core.app:app --host 127.0.0.1 --port 8000
