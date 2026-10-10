"""Turn recording + retention (D5). Pure tests need no DB; DB tests skip without Postgres."""
import pytest
from core import pipeline
from data import retention, transcripts
from data.transcripts import NO_TEXT, record, scrub, session_key, topic
from shared.contracts import Answer, Inquiry

REF = "web_" + "a" * 32
REF2 = "wa_" + "b" * 32
TEST_TOPIC = "zz_test"


def _inq(text="pharmacy in Aley, call me on 70 123 456", ref=REF):
    return Inquiry(id="t", channel="web", text=text, user_ref=ref)


def _ans(tool="directory", outcome="answered", text="Here are 3 pharmacies"):
    return Answer(text=text, tool=tool, outcome=outcome, grounded=True)


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("RECORD_TURNS", "1")
    monkeypatch.setenv("STORE_TRANSCRIPT_TEXT", "1")
    monkeypatch.setattr(transcripts.settings, "session_hash_salt", "a-real-test-salt")
    monkeypatch.setattr(transcripts, "_down_until", 0.0)


# ---- pure ------------------------------------------------------------------
def test_scrub_masks_numbers_and_emails():
    assert "70" not in scrub("call 70 123 456") and "[number]" in scrub("call 70 123 456")
    assert scrub("+961-70-123456") == "[number]" and scrub("رقمي ٧٠١٢٣٤٥٦") == "رقمي [number]"
    assert scrub("mail me at a.b@example.com") == "mail me at [email]"
    assert scrub("Concor 5 mg costs 870,164 LBP") == "Concor 5 mg costs 870,164 LBP"     # not a 7-digit run


def test_topic_comes_from_the_route():
    assert topic(_ans("medicine")) == "drug_price" and topic(_ans("directory")) == "directory"
    assert topic(_ans("procedure")) == "procedures" and topic(_ans("hotline", "unanswered")) == "other"
    assert topic(_ans("hotline", "emergency")) == "emergency" and topic(_ans("hotline", "refused")) == "dosing_request"


def test_session_key_only_for_trusted_refs_and_a_real_salt(monkeypatch):
    monkeypatch.setattr(transcripts.settings, "session_hash_salt", "a-real-test-salt")
    key = session_key(REF)
    assert key and REF not in key and key != session_key(REF2)
    assert session_key("anon") is None and session_key("+96170123456") is None and session_key("") is None
    monkeypatch.setattr(transcripts.settings, "session_hash_salt", "change-me")
    assert session_key(REF) is None


def test_recording_is_off_under_pytest_by_default():
    assert record(_inq(), _ans()) is False


def test_pipeline_records_every_turn_including_early_returns(monkeypatch):
    seen = []
    monkeypatch.setattr(pipeline.transcripts, "record", lambda inq, ans: seen.append((inq.text, ans.outcome)))
    assert pipeline.handle(_inq("my father is not breathing")).outcome == "emergency"
    assert seen == [("my father is not breathing", "emergency")]


def test_db_failure_never_raises_and_backs_off(on, monkeypatch):
    calls = []

    def boom():
        calls.append(1)
        raise RuntimeError("secret row text")
    monkeypatch.setattr(transcripts, "resolve_caza", lambda text: None)
    monkeypatch.setattr(transcripts, "get_conn", boom)
    assert record(_inq(), _ans()) is False
    assert record(_inq(), _ans()) is False
    assert len(calls) == 1                                  # second call skipped, no second timeout


# ---- against Postgres ---------------------------------------------------------
@pytest.fixture
def db(on, monkeypatch):
    from data.db import apply_schema, get_conn
    from data.loaders import load
    try:
        apply_schema()
        load()
        conn = get_conn()
    except Exception:
        pytest.skip("Postgres not reachable")
    monkeypatch.setattr(transcripts, "topic", lambda answer: TEST_TOPIC)
    keys = [session_key(REF), session_key(REF2)]

    def clean():
        conn.execute("DELETE FROM transcripts WHERE session_hash = ANY(%s)", (keys,))
        conn.execute("DELETE FROM metadata WHERE topic = %s", (TEST_TOPIC,))
        conn.commit()
    clean()
    yield conn
    clean()
    conn.close()


def _turns(conn, ref=REF):
    rows = conn.execute("SELECT turn, role, text, outcome, tool FROM transcripts WHERE session_hash = %s ORDER BY turn",
                        (session_key(ref),)).fetchall()
    conn.commit()
    return rows


def _meta(conn):
    rows = conn.execute("SELECT * FROM metadata WHERE topic = %s", (TEST_TOPIC,)).fetchall()
    conn.commit()
    return rows


def _age(conn, ref, interval):
    conn.execute("UPDATE transcripts SET created_at = now() - %s::interval WHERE session_hash = %s",
                 (interval, session_key(ref)))
    conn.commit()


def test_transcripts_table_is_unlogged(db):
    assert db.execute("SELECT relpersistence AS p FROM pg_class WHERE relname = 'transcripts'").fetchone()["p"] == "u"


def test_record_writes_scrubbed_turns_and_one_metadata_row(db):
    assert record(_inq(), _ans()) is True
    assert record(_inq("and in Saida?"), _ans()) is True
    turns = _turns(db)
    assert [(t["turn"], t["role"]) for t in turns] == [(1, "user"), (2, "assistant"), (3, "user"), (4, "assistant")]
    # masked by B's redactor ("[PHONE]") when installed, else by our scrub ("[number]")
    assert turns[0]["text"].startswith("pharmacy in Aley, call me on [") and "123" not in turns[0]["text"]
    assert turns[1]["outcome"] == "answered" and turns[1]["tool"] == "directory"
    meta = _meta(db)
    assert sorted(m["caza"] for m in meta) == ["Aley", "Saida"]
    assert set(meta[0]) == {"topic", "subtopic", "caza", "lang", "outcome", "day"}      # nothing that links to a session


def test_text_is_not_stored_unless_switched_on(db, monkeypatch):
    monkeypatch.delenv("STORE_TRANSCRIPT_TEXT")
    record(_inq(), _ans())
    assert [t["text"] for t in _turns(db)] == [NO_TEXT, NO_TEXT]


def test_emergency_stores_no_text_and_no_caza(db):
    record(_inq("my father in Aley is not breathing"), _ans("hotline", "emergency", "Call 140"))
    assert [t["text"] for t in _turns(db)] == [NO_TEXT, NO_TEXT]
    assert [m["caza"] for m in _meta(db)] == [None]


def test_untrusted_ref_gets_metadata_but_no_transcript(db):
    assert record(_inq(ref="anon"), _ans()) is True
    assert db.execute("SELECT count(*) AS n FROM transcripts WHERE session_hash = 'anon'").fetchone()["n"] == 0
    assert len(_meta(db)) == 1


def test_d5_done_when_idle_transcript_is_deleted_and_metadata_stays(db):
    record(_inq(), _ans())
    record(_inq(ref=REF2), _ans())
    _age(db, REF, "5 minutes")
    assert retention.run_once(idle_minutes=2) >= 2
    assert _turns(db) == []                                 # idle session: gone
    assert len(_turns(db, REF2)) == 2                       # active session: untouched
    assert len(_meta(db)) == 2                              # the anonymous rows remain
    assert retention.run_once(idle_minutes=2) == 0          # nothing left to do


def test_hard_cap_deletes_old_rows_of_an_active_session(db):
    record(_inq(), _ans())
    db.execute("UPDATE transcripts SET created_at = now() - interval '25 hours' WHERE session_hash = %s AND turn = 1",
               (session_key(REF),))
    db.commit()
    retention.run_once(idle_minutes=30)
    assert [t["turn"] for t in _turns(db)] == [2]


def test_status_reports_counts_only(db):
    record(_inq(), _ans())
    s = retention.status()
    assert set(s) == {"transcript_rows", "sessions", "oldest_seconds", "metadata_rows"} and s["transcript_rows"] >= 2
