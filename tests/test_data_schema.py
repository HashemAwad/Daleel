"""Schema checks (D0/D1). Skipped when Postgres isn't reachable, so `pytest` stays
green on a laptop without Docker. With `docker compose up -d` they run for real."""
import psycopg
import pytest
from data.db import get_conn, apply_schema

CONTRACT_TABLES = {"procedures", "facilities", "drugs", "hotlines", "transcripts", "metadata"}


@pytest.fixture(scope="module")
def conn(db_ready):
    c = get_conn()
    yield c
    c.close()


def test_contract_tables_exist(conn):
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    ).fetchall()
    assert CONTRACT_TABLES <= {r["table_name"] for r in rows}


def test_apply_schema_is_idempotent(conn):
    apply_schema()
    apply_schema()


def test_arabic_trigrams_work(conn):
    # In a C locale pg_trgm yields no trigrams for Arabic and this is 0.
    assert conn.execute("SELECT similarity('بنادول', 'بنادول') AS s").fetchone()["s"] == 1.0


def test_metadata_rejects_free_text(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "INSERT INTO metadata (topic, outcome, day) "
            "VALUES ('my number 70123456', 'answered', '2026-10-10')"
        )
    conn.rollback()


@pytest.mark.parametrize("column,value,error", [
    ("subtopic", "John 70123", psycopg.errors.CheckViolation),
    ("lang", "xx", psycopg.errors.CheckViolation),
    ("outcome", "maybe", psycopg.errors.CheckViolation),
    ("topic", "a" * 41, psycopg.errors.CheckViolation),
    ("caza", "Nowhere", psycopg.errors.ForeignKeyViolation),
])
def test_metadata_rejects_out_of_vocabulary_values(conn, column, value, error):
    row = {"topic": "other", "subtopic": None, "caza": None, "lang": None, "outcome": "answered", column: value}
    with pytest.raises(error):
        conn.execute("INSERT INTO metadata (topic, subtopic, caza, lang, outcome, day) "
                     "VALUES (%(topic)s, %(subtopic)s, %(caza)s, %(lang)s, %(outcome)s, '2026-10-10')", row)
    conn.rollback()


def test_metadata_has_no_identifying_columns(conn):
    cols = {r["column_name"] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'metadata'")}
    assert cols == {"topic", "subtopic", "caza", "lang", "outcome", "day"}


def test_transcripts_is_unlogged_and_schema_reapply_keeps_it(conn):
    apply_schema()
    assert conn.execute("SELECT relpersistence AS p FROM pg_class WHERE relname = 'transcripts'").fetchone()["p"] == "u"
    conn.rollback()


def test_transcripts_role_is_checked(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("INSERT INTO transcripts (session_hash, turn, role, text) VALUES ('h', 1, 'admin', 'x')")
    conn.rollback()
