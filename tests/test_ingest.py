"""B1: chunking, language detection, normalization, and DB insert (fake embedder,
so no 2GB model download). DB test skips when Postgres isn't reachable."""
import pytest
from ai import ingest

TEST_URL = "test://ingest-b1"


def _sentences(n, words_each=20, end="."):
    return " ".join(("كلمة " * words_each).strip() + end for _ in range(n))


def test_chunks_respect_size_bounds():
    chunks = ingest.chunk_text(_sentences(100))           # 2000 words
    assert len(chunks) >= 4
    for c in chunks[:-1]:
        assert 300 <= len(c.split()) <= 500
    assert len(chunks[-1].split()) <= 500


def test_chunks_end_on_sentence_boundaries():
    for c in ingest.chunk_text(_sentences(100)):
        assert c.endswith(".")


@pytest.mark.parametrize("end", ["؛", "!", "؟", "،"])
def test_arabic_and_other_boundaries_split(end):
    chunks = ingest.chunk_text(_sentences(100, end=end))
    assert len(chunks) >= 4 and all(c.endswith(end) for c in chunks)


def test_oversize_unpunctuated_text_is_hard_split():
    chunks = ingest.chunk_text("word " * 1200)
    assert len(chunks) == 3 and all(len(c.split()) <= 500 for c in chunks)


def test_short_text_is_one_chunk_and_empty_is_none():
    assert ingest.chunk_text("مرحبا. كيف الحال؟") == ["مرحبا. كيف الحال؟"]
    assert ingest.chunk_text("   ") == []


def test_detect_lang():
    assert ingest.detect_lang("كيف أحصل على بطاقة الضمان الصحي") == "ar"
    assert ingest.detect_lang("Pour obtenir la carte, vous devez déposer le dossier dans le "
                              "centre et les documents de la famille et des enfants pour "
                              "une demande que le ministère traite") == "fr"
    assert ingest.detect_lang("How to get the card") == "en"


def test_normalize_unifies_arabic_variants():
    pytest.importorskip("camel_tools")
    assert ingest.normalize_for_embedding("أدوية") == ingest.normalize_for_embedding("ادويه")
    assert ingest.normalize_for_embedding("Hello") == "Hello"


def test_ingest_text_inserts_and_is_idempotent():
    try:
        from data.db import get_conn
        get_conn().close()
    except Exception:
        pytest.skip("Postgres not reachable")

    def fake_embed(texts):
        return [[1.0] + [0.0] * 1023 for _ in texts]

    text = _sentences(60)                                   # 1200 words -> 3 chunks
    try:
        n1 = ingest.ingest_text(TEST_URL, "Fake page", text, "ar", embed=fake_embed)
        n2 = ingest.ingest_text(TEST_URL, "Fake page", text, "ar", embed=fake_embed)
        with get_conn() as conn:
            row = conn.execute(
                "SELECT count(*) AS n, min(lang) AS lang, bool_and(checked_on IS NOT NULL) AS d,"
                " min(vector_dims(embedding)) AS dims FROM procedures WHERE url = %s",
                (TEST_URL,)).fetchone()
        assert n1 == n2 >= 2
        assert row["n"] == n1                               # re-ingest replaced, not duplicated
        assert row["lang"] == "ar" and row["d"] and row["dims"] == 1024
    finally:
        with get_conn() as conn:
            conn.execute("DELETE FROM procedures WHERE url = %s", (TEST_URL,))


def test_clean_text_strips_site_chrome_only():
    raw = ("Are you a new member?   Sign up now\n\n\t Login area\n | Sign up\n"
           "1- Are all centers entitled to drugs?\nOnly network centers are.")
    out = ingest.clean_text(raw)
    assert out == "1- Are all centers entitled to drugs?\nOnly network centers are."


def test_page_title_prefers_title_tag_over_site_name():
    html = "<html><head><title> PHC - FAQ </title></head></html>"
    assert ingest.page_title(html, "moph", "u") == "PHC - FAQ"
    assert ingest.page_title("<html></html>", "moph", "https://x/y") == "https://x/y"
    assert ingest.page_title("<html></html>", "Real Title", "u") == "Real Title"
