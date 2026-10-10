"""Turn recording + retention (D5). Pure tests need no DB; DB tests use the shared `db_ready` fixture."""
import psycopg
import pytest
from core import pipeline, providers
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
@pytest.mark.parametrize("phone", [
    "70 123 456", "+961-70-123456", "03/123456", "71/123456", "03  123  456", "03_123_456",
    "03‏123456", "(03) 123 456", "70.123.456", "٧٠١٢٣٤٥٦", "٠٣/١٢٣٤٥٦", "123456",
])
def test_scrub_masks_phone_formats(phone):
    out = scrub(f"call me on {phone} please")
    assert out == "call me on [number] please", out


def test_scrub_other_cases():
    assert scrub("mail me at a.b@example.com") == "mail me at [email]"
    assert scrub("a\x00b") == "ab"                                   # Postgres rejects NUL
    assert scrub("Concor 5 mg costs 870,164 LBP") == "Concor 5 mg costs 870,164 LBP"
    assert len(scrub("x" * 50_000)) == transcripts.MAX_TEXT          # bounded, and fast on hostile input
    assert scrub("1-" * 40_000).count("[number]") >= 1


def test_topic_comes_from_the_route():
    assert topic(_ans("medicine")) == "drug_price" and topic(_ans("directory")) == "directory"
    assert topic(_ans("procedure")) == "procedures" and topic(_ans("hotline", "unanswered")) == "other"
    assert topic(_ans("hotline", "emergency")) == "emergency" and topic(_ans("hotline", "refused")) == "dosing_request"


def test_session_key_only_for_trusted_refs_and_a_real_salt(monkeypatch):
    monkeypatch.setattr(transcripts.settings, "session_hash_salt", "a-real-test-salt")
    key = session_key(REF)
    assert key and REF not in key and key != session_key(REF2)
    for bad in ["anon", "+96170123456", "", None, "web_" + "g" * 32, "web_" + "a" * 31, REF + "x"]:
        assert session_key(bad) is None, bad
    for weak in ["change-me", ""]:
        monkeypatch.setattr(transcripts.settings, "session_hash_salt", weak)
        assert session_key(REF) is None, weak


def test_recording_is_off_under_pytest_by_default(monkeypatch):
    monkeypatch.setattr(transcripts, "get_conn", lambda: pytest.fail("must not touch the DB"))
    assert record(_inq(), _ans()) is False


def test_pipeline_records_every_turn_including_early_returns(monkeypatch):
    seen = []
    monkeypatch.setattr(pipeline.transcripts, "record", lambda inq, ans: seen.append((inq.text, ans.outcome)))
    assert pipeline.handle(_inq("my father is not breathing")).outcome == "emergency"
    assert seen == [("my father is not breathing", "emergency")]


def test_pipeline_records_the_transcribed_text_of_a_voice_note(monkeypatch):
    seen = []
    monkeypatch.setattr(pipeline.transcripts, "record", lambda inq, ans: seen.append(inq.text))
    monkeypatch.setattr(pipeline, "_fetch_audio", lambda url: b"audio")

    class Fake:
        def transcribe(self, audio, mime):
            return ("my father is not breathing", "en")
    monkeypatch.setattr(providers, "transcriber", Fake())
    voice = Inquiry(id="t", channel="web", text="", user_ref=REF, audio_url="https://example.com/v.ogg")
    assert pipeline.handle(voice).outcome == "emergency"
    assert seen == ["my father is not breathing"]              # not "", so caza and text can be recorded


def test_db_outage_never_raises_and_backs_off(on, monkeypatch):
    calls = []

    def down():
        calls.append(1)
        raise psycopg.OperationalError("connection refused: secret")
    monkeypatch.setattr(transcripts, "resolve_caza", lambda text: None)
    monkeypatch.setattr(transcripts, "get_conn", down)
    assert record(_inq(), _ans()) is False
    assert record(_inq(), _ans()) is False
    assert len(calls) == 1                                  # second call skipped: no second timeout


def test_one_bad_turn_does_not_silence_the_next(on, monkeypatch):
    calls = []

    def broken():
        calls.append(1)
        raise ValueError("not an outage")
    monkeypatch.setattr(transcripts, "resolve_caza", lambda text: None)
    monkeypatch.setattr(transcripts, "get_conn", broken)
    assert record(_inq(), _ans()) is False
    assert record(_inq(), _ans()) is False
    assert len(calls) == 2                                  # no back-off for a non-outage error


# ---- against Postgres ---------------------------------------------------------
@pytest.fixture
def db(db_ready, on, monkeypatch):
    from data.db import get_conn
    conn = get_conn()
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


def _count(conn, table):
    n = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
    conn.commit()
    return n


def _age(conn, ref, interval):
    conn.execute("UPDATE transcripts SET created_at = now() - %s::interval WHERE session_hash = %s",
                 (interval, session_key(ref)))
    conn.commit()


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
    assert set(meta[0]) == {"topic", "subtopic", "caza", "lang", "outcome", "day"}      # no session key, no timestamp


def test_scrub_is_the_backstop_when_the_redactor_does_nothing(db, monkeypatch):
    monkeypatch.setattr(providers, "redact", lambda text: text)
    record(_inq("ring 03/123456"), _ans())
    assert _turns(db)[0]["text"] == "ring [number]"


def test_no_text_is_stored_when_the_redactor_fails(db, monkeypatch):
    def boom(text):
        raise RuntimeError("redactor crashed")
    monkeypatch.setattr(providers, "redact", boom)
    assert record(_inq(), _ans()) is True
    assert [t["text"] for t in _turns(db)] == [NO_TEXT, NO_TEXT]


def test_text_is_not_stored_unless_switched_on(db, monkeypatch):
    monkeypatch.delenv("STORE_TRANSCRIPT_TEXT")
    record(_inq(), _ans())
    assert [t["text"] for t in _turns(db)] == [NO_TEXT, NO_TEXT]


@pytest.mark.parametrize("outcome", ["emergency", "refused"])
def test_emergency_and_refusal_store_no_text_and_no_caza(db, outcome):
    record(_inq("my father in Aley, what dose, he is not breathing 70 123 456"), _ans("hotline", outcome, "Call 140"))
    assert [t["text"] for t in _turns(db)] == [NO_TEXT, NO_TEXT]
    assert [m["caza"] for m in _meta(db)] == [None]


@pytest.mark.parametrize("ref", ["anon", "+96170123456", "web_forged"])
def test_untrusted_ref_gets_metadata_but_no_transcript(db, ref):
    before = _count(db, "transcripts")
    assert record(_inq(ref=ref), _ans()) is True
    assert _count(db, "transcripts") == before               # nothing stored under ANY key
    assert len(_meta(db)) == 1


def test_default_salt_stores_no_transcript(db, monkeypatch):
    monkeypatch.setattr(transcripts.settings, "session_hash_salt", "change-me")
    before = _count(db, "transcripts")
    assert record(_inq(), _ans()) is True
    assert _count(db, "transcripts") == before and len(_meta(db)) == 1


def test_a_nul_character_does_not_lose_the_turn(db):
    assert record(_inq("pharmacy in Aley\x00"), _ans()) is True
    assert len(_turns(db)) == 2 and len(_meta(db)) == 1


def test_metadata_survives_a_transcript_write_failure(db, monkeypatch):
    monkeypatch.setattr(transcripts, "_INSERT_TURN", "INSERT INTO no_such_table VALUES (%s,%s,%s,%s,%s,%s,%s)")
    assert record(_inq(), _ans()) is False
    assert len(_meta(db)) == 1 and _turns(db) == []           # the count is kept; nothing half-written
    assert transcripts._down_until == 0.0                     # and it was not treated as an outage


def test_d5_done_when_idle_transcript_is_deleted_and_metadata_stays(db):
    record(_inq(), _ans())
    record(_inq(ref=REF2), _ans())
    _age(db, REF, "5 minutes")
    _age(db, REF2, "1 minute")                               # idle, but inside the 2-minute window
    assert retention.run_once(idle_minutes=2) >= 2
    assert _turns(db) == []                                 # idle past the window: gone
    assert len(_turns(db, REF2)) == 2                       # one minute idle: untouched (minutes, not seconds)
    assert len(_meta(db)) == 2                              # the anonymous rows remain
    assert retention.run_once(idle_minutes=2) == 0          # nothing left to do


def test_run_once_defaults_to_the_configured_window(db, monkeypatch):
    record(_inq(), _ans())
    _age(db, REF, "5 minutes")
    monkeypatch.setattr(retention.settings, "retention_idle_minutes", 30)
    retention.run_once()
    assert len(_turns(db)) == 2                             # 5 minutes < 30
    monkeypatch.setattr(retention.settings, "retention_idle_minutes", 2)
    retention.run_once()
    assert _turns(db) == []


def test_hard_cap_deletes_old_rows_of_an_active_session(db):
    record(_inq(), _ans())
    db.execute("UPDATE transcripts SET created_at = now() - interval '25 hours' WHERE session_hash = %s AND turn = 1",
               (session_key(REF),))
    db.commit()
    retention.run_once(idle_minutes=30)
    assert [t["turn"] for t in _turns(db)] == [2]


def test_status_reports_counts_only_and_flags_overdue_sessions(db, monkeypatch):
    monkeypatch.setattr(retention.settings, "retention_idle_minutes", 2)
    monkeypatch.setenv("RETENTION_INTERVAL_SECONDS", "20")
    record(_inq(), _ans())
    s = retention.status()
    assert set(s) == {"transcript_rows", "sessions", "oldest_seconds", "overdue_sessions", "metadata_rows"}
    assert s["transcript_rows"] >= 2
    overdue_before = s["overdue_sessions"]
    _age(db, REF, "10 minutes")                              # the loop should have removed this by now
    assert retention.status()["overdue_sessions"] == overdue_before + 1
