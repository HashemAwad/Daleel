"""Schema checks (D0/D1). Skipped when Postgres isn't reachable, so `pytest` stays
green on a laptop without Docker. With `docker compose up -d` they run for real."""
import psycopg
import pytest
from data.db import get_conn, apply_schema

CONTRACT_TABLES = {"procedures", "facilities", "drugs", "hotlines", "transcripts", "metadata"}


@pytest.fixture(scope="module")
def conn():
    try:
        apply_schema()
        c = get_conn()
    except Exception:
        pytest.skip("Postgres not reachable")
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


def test_transcripts_role_is_checked(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("INSERT INTO transcripts (session_hash, turn, role, text) VALUES ('h', 1, 'admin', 'x')")
    conn.rollback()
