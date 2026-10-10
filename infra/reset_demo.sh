#!/usr/bin/env bash
# Reset Daleel to a known demo state. Owner: D.
#   bash infra/reset_demo.sh              reload seeds, clear transcripts + metadata, add SAMPLE metadata
#   bash infra/reset_demo.sh --no-sample  same, but leave metadata empty
# Deletes every transcript and metadata row. Sample rows are made up and marked subtopic='sample'.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
PYTHONPATH=src "$PY" -m data.demo --yes "$@"
PYTHONPATH=src "$PY" -m data.retention --status
