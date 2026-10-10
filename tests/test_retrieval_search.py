"""B2: ProcedureSearchImpl nearest-neighbour search (fake embedder, no model download).
Skips when Postgres isn't reachable."""
import pytest
from ai import ingest, retrieval

URLS = ["test://b2-a", "test://b2-b"]


def _vec(i):
    v = [0.0] * 1024
    v[i] = 1.0
    return v


def _fake_embed(texts):
    return [_vec(0) if "alpha" in t else _vec(1) for t in texts]


@pytest.fixture(scope="module", autouse=True)
def _rows():
    try:
        retrieval.ping()
    except Exception:
        pytest.skip("Postgres not reachable")
    from data.db import get_conn
    ingest.ingest_text(URLS[0], "Title A", "alpha text.", "en", embed=_fake_embed)
    ingest.ingest_text(URLS[1], "Title B", "beta text.", "ar", embed=_fake_embed)
    yield
    with get_conn() as conn:
        conn.execute("DELETE FROM procedures WHERE url = ANY(%s)", (URLS,))


def test_nearest_doc_first_with_source_and_score():
    docs = retrieval.ProcedureSearchImpl(embed=_fake_embed).search("alpha", k=2)
    assert docs[0].title == "Title A"
    assert docs[0].source.url == URLS[0] and docs[0].source.checked_on
    assert docs[0].lang == "en"
    assert docs[0].score == pytest.approx(1.0, abs=1e-4)
    assert docs[0].score > docs[1].score


def test_k_limits_results():
    assert len(retrieval.ProcedureSearchImpl(embed=_fake_embed).search("alpha", k=1)) == 1


def test_lang_does_not_filter():
    """Arabizi/FR queries must still match AR/EN pages."""
    docs = retrieval.ProcedureSearchImpl(embed=_fake_embed).search("beta", lang="arabizi", k=1)
    assert docs[0].title == "Title B"
