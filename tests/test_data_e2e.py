"""End to end through the real HTTP app: /chat -> pipeline -> data layer -> Postgres -> retention.

The model is pinned to the stub so results don't depend on which LLM is installed; everything
in src/data runs for real against the seed data. Needs Postgres (shared `db_ready` fixture)."""
import pytest
from fastapi.testclient import TestClient
from core import providers, stubs
from data import directory, retention, transcripts
from data.transcripts import NO_TEXT, session_key

PREFIX = "zz_ete_"       # letters and underscores only: the topic CHECK rejects digits


@pytest.fixture
def app(db_ready, monkeypatch):
    from core.app import app as fastapi_app
    from data.directory import DirectorySearchImpl
    from data.medicine import MedicineLookupImpl
    monkeypatch.setenv("RECORD_TURNS", "1")
    monkeypatch.setenv("STORE_TRANSCRIPT_TEXT", "1")
    monkeypatch.delenv("MODEL_ROUTER", raising=False)
    monkeypatch.setattr(transcripts.settings, "session_hash_salt", "a-real-test-salt")
    monkeypatch.setattr(transcripts, "_down_until", 0.0)
    monkeypatch.setattr(directory, "_tables", None)
    monkeypatch.setattr(providers, "llm", stubs.StubLLM())
    monkeypatch.setattr(providers, "medicine", MedicineLookupImpl())
    monkeypatch.setattr(providers, "directory", DirectorySearchImpl())
    real_topic = transcripts.topic
    monkeypatch.setattr(transcripts, "topic", lambda answer: PREFIX + real_topic(answer))   # so we can clean up
    yield TestClient(fastapi_app)
    from data.db import get_conn
    with get_conn() as conn:
        conn.execute("DELETE FROM metadata WHERE topic LIKE %s", (PREFIX + "%",))


@pytest.fixture
def session(app):
    ref = app.get("/api/session").json()["user_ref"]
    yield ref
    from data.db import get_conn
    with get_conn() as conn:
        conn.execute("DELETE FROM transcripts WHERE session_hash = %s", (session_key(ref),))


def _ask(app, ref, text, **extra):
    r = app.post("/chat", json={"channel": "web", "text": text, "user_ref": ref, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _rows(sql, *params):
    from data.db import get_conn
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def _topics():
    return sorted(r["topic"][len(PREFIX):] for r in _rows("SELECT topic FROM metadata WHERE topic LIKE %s", PREFIX + "%"))


def test_price_question_returns_the_exact_strength_price(app, session):
    a = _ask(app, session, "Combien coûte le Concor 5?")
    assert a["tool"] == "medicine" and a["grounded"] is True and a["outcome"] == "answered"
    assert "870164" in a["text"] and "1176665" not in a["text"]           # 5mg price, never the 10mg one


@pytest.mark.parametrize("question,forbidden", [
    ("how much is aspirin", "146479"),                 # only ASPIRIN PROTECT exists: its price must not be quoted
    ("diamicron price", "382995"),
    ("price of concor for 10 people", "1176665"),      # 10 is not a strength
    ("how much is concor", "870164"),                  # two strengths: ask which
])
def test_no_price_is_quoted_for_a_product_the_user_did_not_name(app, session, question, forbidden):
    a = _ask(app, session, question)
    assert forbidden not in a["text"], a["text"]


def test_unknown_drug_or_strength_gets_the_hotline_not_a_guess(app, session):
    for question in ["price of lipitor", "price of concor 20"]:
        a = _ask(app, session, question)
        assert a["grounded"] is False and a["outcome"] == "unanswered" and "1787" in a["text"], question


def test_directory_question_in_arabizi_returns_real_aley_pharmacies(app, session):
    a = _ask(app, session, "bade saydaliyye 2arib mn Aley")
    assert a["tool"] == "directory" and a["outcome"] == "answered" and a["grounded"] is True
    assert "Aley" in a["text"]


def test_directory_question_without_a_place_asks_for_the_town(app, session):
    a = _ask(app, session, "nearest pharmacy")
    assert a["tool"] == "directory" and a["outcome"] == "unanswered" and a["grounded"] is False


def test_directory_outage_gives_the_hotline_not_an_endless_town_question(app, session, monkeypatch):
    def down():
        raise RuntimeError("db down")
    monkeypatch.setattr(directory, "get_conn", down)
    a = _ask(app, session, "nearest pharmacy in Aley")
    # The reply still gives the hotline, but keeps the failed topic so analytics
    # can show that a directory question went unanswered.
    assert a["tool"] == "directory" and "1787" in a["text"]


def test_shared_location_ranks_by_distance(app, session):
    a = _ask(app, session, "nearest pharmacy", lat=33.81, lon=35.60)
    assert a["tool"] == "directory" and a["outcome"] == "answered" and "km" in a["text"]


def test_a_whole_conversation_is_recorded_scrubbed_then_deleted(app, session):
    _ask(app, session, "Combien coûte le Concor 5? appelez-moi au 03/123456")
    _ask(app, session, "my father in Aley is not breathing, his number is 70 123 456")
    _ask(app, session, "bade saydaliyye 2arib mn Aley")
    key = session_key(session)

    turns = _rows("SELECT turn, role, text, outcome, tool FROM transcripts WHERE session_hash = %s ORDER BY turn", key)
    assert [t["role"] for t in turns] == ["user", "assistant"] * 3
    stored = " ".join(t["text"] for t in turns)
    assert "123456" not in stored and "123 456" not in stored             # no phone number survives
    assert session not in stored and key not in stored
    assert [turns[2]["text"], turns[3]["text"]] == [NO_TEXT, NO_TEXT]     # the emergency turn: no text at all
    assert turns[3]["outcome"] == "emergency" and turns[5]["tool"] == "directory"

    assert _topics() == ["directory", "drug_price", "emergency"]          # one anonymous row per turn
    meta = _rows("SELECT * FROM metadata WHERE topic LIKE %s", PREFIX + "%")
    by_topic = {m["topic"][len(PREFIX):]: m for m in meta}
    assert by_topic["directory"]["caza"] == "Aley"
    assert by_topic["emergency"]["caza"] is None                          # never a place on an emergency row
    assert all(set(m) == {"topic", "subtopic", "caza", "lang", "outcome", "day"} for m in meta)

    _rows("UPDATE transcripts SET created_at = now() - interval '10 minutes' WHERE session_hash = %s RETURNING 1", key)
    assert retention.run_once(idle_minutes=2) >= 6
    assert _rows("SELECT 1 FROM transcripts WHERE session_hash = %s", key) == []
    assert _topics() == ["directory", "drug_price", "emergency"]          # the counts outlive the text


def test_forged_and_anonymous_refs_are_answered_but_never_stored(app):
    before = _rows("SELECT count(*) AS n FROM transcripts")[0]["n"]
    for ref in ["anon", "+96170123456", "web_not-a-real-ref"]:
        assert _ask(app, ref, "Combien coûte le Concor 5?")["tool"] == "medicine"
    assert _rows("SELECT count(*) AS n FROM transcripts")[0]["n"] == before
    assert _topics() == ["drug_price"] * 3


def test_recording_failure_never_breaks_the_reply(app, session, monkeypatch):
    def down():
        raise RuntimeError("db down")
    monkeypatch.setattr(transcripts, "get_conn", down)
    monkeypatch.setattr(transcripts, "resolve_caza", lambda text: None)
    a = _ask(app, session, "my father is not breathing")
    assert a["outcome"] == "emergency" and "140" in a["text"]
