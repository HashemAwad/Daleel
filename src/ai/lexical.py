"""Lexical (keyword) procedure ingestion + search — the no-ML-download half of
the hybrid retrieval. Owner: A (Phase 0), coordinates with B's vector path.

Why this exists: B's semantic search needs `sentence_transformers` + the ~2.3GB
bge-m3 model. Until those are installed, procedures must still answer. This
module ingests REAL page text with a NULL embedding (the column is nullable) and
searches it with Postgres `pg_trgm` word-similarity — accurate for same-language
queries, offline, instant. When the embedding model is present, B's vector search
in retrieval.py takes over automatically (it only reads rows WHERE embedding IS
NOT NULL); this is the fallback.

Ingest real pages:
    PYTHONPATH=src python -m ai.lexical https://moph.gov.lb/... [--lang ar]
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.db import get_conn
from shared.contracts import Doc, Lang, Source

# word_similarity(query, doc) in [0,1]; 0.30 keeps real matches and drops
# off-topic questions so the grounding gate falls back instead of guessing.
LEXICAL_MIN_SCORE = float(os.getenv("PROCEDURE_LEXICAL_MIN_SCORE", "0.30"))


# ---------------------------------------------------------------- ingest
def ingest_lexical(url: str, lang: Optional[str] = None) -> int:
    """Fetch a real page, chunk it, store text with NULL embedding. Returns chunks stored.
    Re-ingesting a URL replaces its rows (no duplicates)."""
    from ai.ingest import fetch_page, chunk_text, detect_lang

    page = fetch_page(url)
    if page is None:
        return 0
    title, text = page
    chunks = chunk_text(text)
    if not chunks:
        return 0
    lang = lang or detect_lang(text)
    today = date.today()
    with get_conn() as conn:
        conn.execute("DELETE FROM procedures WHERE url = %s", (url,))
        for chunk in chunks:
            conn.execute(
                "INSERT INTO procedures (title, content, url, checked_on, lang, embedding)"
                " VALUES (%s, %s, %s, %s, %s, NULL)",
                (title, chunk, url, today, lang))
    return len(chunks)


# ---------------------------------------------------------------- search
def lexical_search(query: str, k: int = 4, min_score: Optional[float] = None,
                   only_without_embedding: bool = False) -> list[Doc]:
    """pg_trgm word-similarity over title+content. Language-agnostic exact-ish
    matching (no stemming); cross-language matching is the vector path's job."""
    floor = LEXICAL_MIN_SCORE if min_score is None else min_score
    with get_conn() as conn:
        where = " WHERE embedding IS NULL" if only_without_embedding else ""
        rows = conn.execute(
            "SELECT id, title, content, url, checked_on, lang,"
            " word_similarity(%s, title || ' ' || content) AS score"
            " FROM procedures" + where +
            " ORDER BY score DESC LIMIT %s",
            (query, k)).fetchall()
    return [Doc(id=str(r["id"]), title=r["title"], content=r["content"], lang=r["lang"],
                score=float(r["score"]),
                source=Source(title=r["title"], url=r["url"],
                              checked_on=r["checked_on"].isoformat() if r["checked_on"] else None))
            for r in rows if float(r["score"]) >= floor]


def main(argv: list[str]) -> int:
    lang = None
    if "--lang" in argv:
        i = argv.index("--lang")
        lang = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    urls = [a for a in argv if a.startswith("http")]
    if not urls:
        print("usage: python -m ai.lexical URL [URL ...] [--lang ar|fr|en]")
        return 2
    total = 0
    for url in urls:
        n = ingest_lexical(url, lang)
        print(f"{url}: {n} chunks" if n else f"{url}: nothing fetched/extracted")
        total += n
    print(f"total chunks inserted: {total}")
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
