"""Procedure ingestion (B1). Owner: B.

    PYTHONPATH=src python src/ai/ingest.py URL [URL ...] [--lang ar|fr|en]

fetch (Trafilatura) -> clean -> sentence-aware chunks (~300-500 words) -> embed
(BAAI/bge-m3, normalized) -> insert into `procedures`.

Approach (chunk -> embed -> insert pipeline) follows RahulModugula/athena (MIT).
Re-running for a URL replaces that URL's rows, so refreshing a page never duplicates it.
We EMBED the Arabic-normalized text but STORE the original text, so users see clean
source wording. B2 must apply the same `normalize_for_embedding` to queries.
Never print page text or exception messages here.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from typing import Callable, Optional

if __package__ in (None, ""):                       # allow `python src/ai/ingest.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

EMBED_MODEL = "BAAI/bge-m3"          # 1024 dims = procedures.embedding vector(1024)
MIN_WORDS, MAX_WORDS = 300, 500

# Sentence ends: . ؛ ! ؟ ? ، followed by whitespace. (، is a comma, but the ticket asks
# for it, and it keeps Arabic run-on sentences from becoming one giant chunk.)
_SENT_SPLIT = re.compile(r"(?<=[.؛!؟?،])\s+")
_ARABIC = re.compile(r"[؀-ۿ]")
_FR_HINT = re.compile(r"\b(le|la|les|des|du|de|et|pour|vous|est|une|un|dans|que|sur)\b", re.I)


# ---------------------------------------------------------------- text helpers
def normalize_for_embedding(text: str) -> str:
    """Arabic orthographic normalization (camel_tools): strips diacritics, unifies
    alef / alef-maksura / teh-marbuta variants. No-op on Latin text."""
    from camel_tools.utils.dediac import dediac_ar
    from camel_tools.utils.normalize import (
        normalize_alef_ar, normalize_alef_maksura_ar, normalize_teh_marbuta_ar)
    t = dediac_ar(text)
    return normalize_teh_marbuta_ar(normalize_alef_maksura_ar(normalize_alef_ar(t)))


def detect_lang(text: str) -> str:
    """Cheap heuristic: mostly-Arabic script -> 'ar', French function words -> 'fr', else 'en'.
    Pages are curated, so `--lang` overrides this."""
    letters = [c for c in text if c.isalpha()]
    if letters and sum(1 for c in letters if _ARABIC.match(c)) / len(letters) > 0.5:
        return "ar"
    return "fr" if len(_FR_HINT.findall(text[:3000])) >= 8 else "en"


def _word_count(s: str) -> int:
    return len(s.split())


def chunk_text(text: str, min_words: int = MIN_WORDS, max_words: int = MAX_WORDS) -> list[str]:
    """Greedy-pack whole sentences until adding the next would exceed max_words.
    A chunk is closed once it has >= min_words. A short final chunk is merged into the
    previous one if that stays <= max_words. A single over-long 'sentence' (e.g. a table
    with no punctuation) is hard-split on words so nothing exceeds max_words."""
    sentences: list[str] = []
    for s in _SENT_SPLIT.split(text.strip()):
        s = s.strip()
        if not s:
            continue
        words = s.split()
        for i in range(0, len(words), max_words):      # hard-split oversize sentences
            sentences.append(" ".join(words[i:i + max_words]))

    chunks: list[list[str]] = []
    cur: list[str] = []
    cur_n = 0
    for s in sentences:
        n = _word_count(s)
        if cur and cur_n + n > max_words:
            chunks.append(cur)
            cur, cur_n = [], 0
        cur.append(s)
        cur_n += n
        if cur_n >= min_words:
            chunks.append(cur)
            cur, cur_n = [], 0
    if cur:
        tail_n = sum(_word_count(x) for x in cur)
        if chunks and sum(_word_count(x) for x in chunks[-1]) + tail_n <= max_words:
            chunks[-1].extend(cur)
        else:
            chunks.append(cur)
    return [" ".join(c) for c in chunks]


# Site chrome that Trafilatura keeps on moph.gov.lb pages (login banner). Whole-line match,
# case-insensitive. Add patterns here if new pages leak other navigation text.
_BOILERPLATE = re.compile(
    r"^\s*(are you a new member\?.*|sign up( now)?|login area|\|?\s*sign up|login|close)\s*$", re.I)
_TITLE_TAG = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def clean_text(text: str) -> str:
    """Drop site-chrome lines and collapse blank/space runs. Keeps paragraph breaks."""
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    kept = [ln for ln in lines if ln and not _BOILERPLATE.match(ln)]
    return "\n".join(kept)


def page_title(html: str, meta_title: Optional[str], url: str) -> str:
    """Prefer the page's <title>; Trafilatura's title is just the site name ('moph') here."""
    m = _TITLE_TAG.search(html)
    cand = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    for t in (cand, (meta_title or "").strip()):
        if t and t.lower() not in {"moph", "moph.gov.lb"}:
            return t
    return url


# ---------------------------------------------------------------- fetch / embed
def fetch_page(url: str) -> Optional[tuple[str, str]]:
    """(title, main text) via Trafilatura, or None if the fetch/extract yields nothing."""
    import trafilatura
    html = trafilatura.fetch_url(url)
    if not html:
        return None
    text = trafilatura.extract(html, include_comments=False, include_tables=True,
                               favor_recall=True)
    if not text:
        return None
    meta = trafilatura.extract_metadata(html)
    text = clean_text(text)
    if not text:
        return None
    return page_title(html, meta.title if meta else None, url), text


_model = None


def embed_texts(texts: list[str]) -> list[list[float]]:
    """bge-m3 dense embeddings, L2-normalized (so cosine == dot product)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBED_MODEL)
    vecs = _model.encode([normalize_for_embedding(t) for t in texts],
                         normalize_embeddings=True, batch_size=8)
    return [v.tolist() for v in vecs]


# ---------------------------------------------------------------- insert
def ingest_text(url: str, title: str, text: str, lang: Optional[str] = None,
                embed: Callable[[list[str]], list[list[float]]] = embed_texts,
                checked_on: Optional[date] = None) -> int:
    """Chunk + embed + insert one page; returns number of chunks stored."""
    from pgvector.psycopg import register_vector
    from data.db import get_conn

    lang = lang or detect_lang(text)
    chunks = chunk_text(text)
    if not chunks:
        return 0
    vectors = embed(chunks)
    checked_on = checked_on or date.today()
    import numpy as np
    with get_conn() as conn:
        register_vector(conn)
        conn.execute("DELETE FROM procedures WHERE url = %s", (url,))
        for chunk, vec in zip(chunks, vectors):
            conn.execute(
                "INSERT INTO procedures (title, content, url, checked_on, lang, embedding)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                (title, chunk, url, checked_on, lang, np.asarray(vec, dtype=np.float32)))
    return len(chunks)


def ingest_url(url: str, lang: Optional[str] = None) -> int:
    page = fetch_page(url)
    if page is None:
        return 0
    title, text = page
    return ingest_text(url, title, text, lang)


def main(argv: list[str]) -> int:
    lang = None
    if "--lang" in argv:
        i = argv.index("--lang")
        lang = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    urls = [a for a in argv if a.startswith("http")]
    if not urls:
        print("usage: python src/ai/ingest.py URL [URL ...] [--lang ar|fr|en]")
        return 2
    total = 0
    for url in urls:
        n = ingest_url(url, lang)
        print(f"{url}: {n} chunks" if n else f"{url}: nothing fetched/extracted")
        total += n
    print(f"total chunks inserted: {total}")
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
