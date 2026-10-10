"""Procedure retrieval. Owner: B.

B0: DB connectivity only. `ProcedureSearchImpl` is added in B2 — it is deliberately
absent now so core/providers.py keeps the stub instead of swapping in an empty search.

Never log exception messages or query text from here (Postgres errors can echo rows).
"""
from __future__ import annotations

from data.db import get_conn


def ping() -> bool:
    """True if the DB answers a trivial SELECT."""
    with get_conn() as conn:
        return conn.execute("SELECT 1 AS ok").fetchone()["ok"] == 1


def count_procedures() -> int:
    """Row count of `procedures` (0 is fine — the table may be empty before B1)."""
    with get_conn() as conn:
        return conn.execute("SELECT count(*) AS n FROM procedures").fetchone()["n"]


if __name__ == "__main__":
    print(f"db ok={ping()} procedures={count_procedures()}")
