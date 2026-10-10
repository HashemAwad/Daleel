"""Procedure retrieval. Owner: B.

B0: DB connectivity. B2: `ProcedureSearchImpl` — pgvector cosine nearest-neighbour over
`procedures` (bge-m3, same query normalization as ingest). core/providers.py auto-detects it.

Never log exception messages or query text from here (Postgres errors can echo rows).
"""
from __future__ import annotations

import os
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


# bge-m3 cosine similarity. Measured on the PHC FAQ page: off-topic questions (capital of
# France, recipes, weather; AR/FR/EN) score 0.26-0.32, on-topic ones 0.44-0.54. Re-check this
# when more pages are ingested. Override with PROCEDURE_MIN_SCORE.
DEFAULT_MIN_SCORE = 0.38


class ProcedureSearchImpl:
    """Implements shared.contracts.ProcedureSearch.

    `lang` is accepted for the contract but NOT used as a filter: bge-m3 is multilingual,
    so Arabizi / French / English queries should match Arabic pages and vice versa.

    Results scoring below `min_score` are dropped, so an off-topic question returns [] and
    core's grounding gate falls back to the hotline instead of answering from a weak match.
    """

    def __init__(self, embed: Optional[Callable[[list[str]], list[list[float]]]] = None,
                 min_score: Optional[float] = None):
        self._embed = embed
        self._min_score = (min_score if min_score is not None
                           else float(os.getenv("PROCEDURE_MIN_SCORE", DEFAULT_MIN_SCORE)))

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
                for r in rows if float(r["score"]) >= self._min_score]


if __name__ == "__main__":
    print(f"db ok={ping()} procedures={count_procedures()}")
