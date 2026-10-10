"""Retention job: delete temporary transcripts. Owner: D.

    PYTHONPATH=src python -m data.retention --once      # one sweep now (use this live on stage)
    PYTHONPATH=src python -m data.retention --loop      # sweep at start, then every RETENTION_INTERVAL_SECONDS
    PYTHONPATH=src python -m data.retention --status    # counts + oldest age, never text; exit 1 if over the cap

The anonymous metadata row was already written when the turn happened (data.transcripts.record),
so this job only deletes:
  1. every row of a session that has been idle longer than RETENTION_IDLE_MINUTES
  2. any row older than 24 hours, whatever its session is doing (hard cap)
Logs counts only.
"""
from __future__ import annotations
import argparse
import logging
import os
import sys
import time
from data.db import get_conn
from shared.config import settings

log = logging.getLogger(__name__)
HARD_CAP_HOURS = 24

_DELETE_IDLE = (
    "DELETE FROM transcripts WHERE session_hash IN ("
    "  SELECT session_hash FROM transcripts GROUP BY session_hash"
    "  HAVING max(created_at) < now() - make_interval(mins => %s))"
)
_DELETE_OLD = "DELETE FROM transcripts WHERE created_at < now() - make_interval(hours => %s)"


def run_once(idle_minutes: int | None = None) -> int:
    """Delete due transcript rows; returns how many. All ages use the database clock."""
    idle = settings.retention_idle_minutes if idle_minutes is None else idle_minutes
    with get_conn() as conn:
        deleted = conn.execute(_DELETE_IDLE, (idle,)).rowcount
        deleted += conn.execute(_DELETE_OLD, (HARD_CAP_HOURS,)).rowcount
    return deleted


def status() -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT count(*) AS transcript_rows, count(DISTINCT session_hash) AS sessions, "
            "COALESCE(EXTRACT(EPOCH FROM now() - min(created_at)), 0)::int AS oldest_seconds FROM transcripts"
        ).fetchone()
        row["metadata_rows"] = conn.execute("SELECT count(*) AS n FROM metadata").fetchone()["n"]
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description="Daleel transcript retention")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--loop", action="store_true")
    mode.add_argument("--status", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    if args.status:
        s = status()
        print(s)
        return 1 if s["oldest_seconds"] > HARD_CAP_HOURS * 3600 + 600 else 0
    if args.once:
        print(f"deleted {run_once()} transcript rows")
        return 0
    interval = int(os.getenv("RETENTION_INTERVAL_SECONDS", "600"))
    while True:
        try:
            log.info("deleted %d transcript rows", run_once())
        except Exception as e:
            log.warning("retention sweep failed: %s", type(e).__name__)
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
