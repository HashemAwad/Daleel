"""DB access + idempotent schema apply. Owner: D.

No connection is opened at import: core/providers.py silently swaps in a stub when an
import raises, so a down DB must surface as an empty result, not as a fake answer.
Never log exception *messages* from DB calls — Postgres errors can echo the row.

    with get_conn() as conn:
        conn.execute("SELECT 1")          # commits on exit, closes the connection

Re-apply the schema to a running DB (idempotent):  PYTHONPATH=src python -m data.db
"""
from __future__ import annotations
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from shared.config import settings

SCHEMA_PATH = Path(__file__).parent / "init" / "schema.sql"


# ponytail: one connection per call. Fine for demo load; add psycopg_pool if latency bites.
def get_conn() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, row_factory=dict_row, connect_timeout=3)


def apply_schema() -> None:
    with get_conn() as conn:
        conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    apply_schema()
    print("schema applied")
