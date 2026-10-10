"""Procedure retrieval. Owner: B.

B0: DB connectivity. B2: `ProcedureSearchImpl` — pgvector cosine nearest-neighbour over
`procedures` (bge-m3, same query normalization as ingest). core/providers.py auto-detects it.

Never log exception messages or query text from here (Postgres errors can echo rows).
"""
from __future__ import annotations

from typing import Callable, Optional

from data.db import get_conn
from shared.contracts import Doc, Lang, Source


def ping() -> bool:
    """True if the DB answers a trivial SELECT."""
    with get_conn() as conn:
        return conn.execute("SELECT 1 AS ok").fetchone()["ok"] == 1


def count_procedures() -> int:
    """Row count of `procedures` (0 is fine — the table may be empty before B1)."""
    with get_conn() as conn:
        return conn.execute("SELECT count(*) AS n FROM procedures").fetchone()["n"]


class ProcedureSearchImpl:
    """Implements shared.contracts.ProcedureSearch.

    `lang` is accepted for the contract but NOT used as a filter: bge-m3 is multilingual,
    so Arabizi / French / English queries should match Arabic pages and vice versa.
    """

    def __init__(self, embed: Optional[Callable[[list[str]], list[list[float]]]] = None):
        self._embed = embed

    def search(self, query: str, lang: Optional[Lang] = None, k: int = 4) -> list[Doc]:
        import numpy as np
        from pgvector.psycopg import register_vector
        embed = self._embed
        if embed is None:
            from ai.ingest import embed_texts as embed   # lazy: loads the model on first use
        qvec = np.asarray(embed([query])[0], dtype=np.float32)
        with get_conn() as conn:
            register_vector(conn)
            rows = conn.execute(
                "SELECT id, title, content, url, checked_on, lang,"
                " 1 - (embedding <=> %s) AS score"
                " FROM procedures WHERE embedding IS NOT NULL"
                " ORDER BY embedding <=> %s LIMIT %s",
                (qvec, qvec, k)).fetchall()
        return [Doc(id=str(r["id"]), title=r["title"], content=r["content"], lang=r["lang"],
                    score=float(r["score"]),
                    source=Source(title=r["title"], url=r["url"],
                                  checked_on=r["checked_on"].isoformat() if r["checked_on"] else None))
                for r in rows]


if __name__ == "__main__":
    print(f"db ok={ping()} procedures={count_procedures()}")
