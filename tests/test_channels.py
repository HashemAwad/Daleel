"""Dev C channel tests: WhatsApp webhook, voice intake, privacy, dashboard API.

Run: PYTHONPATH=src pytest -q
"""
import pytest
from fastapi.testclient import TestClient

from channels import identity, metrics, register, render, whatsapp
from channels.asgi import app
from channels.settings_extra import channel_settings
from shared.config import settings
from shared.contracts import Answer, Source

client = TestClient(app)

PHONE = "whatsapp:+96170123456"
TOKEN = "test-auth-token"
URL = "http://testserver" + whatsapp.WEBHOOK_PATH


def form(**over) -> dict:
    base = {
        "From": PHONE, "To": "whatsapp:+14155238886", "Body": "how do I renew my medication card?",
        "MessageSid": "SM123", "AccountSid": "AC123", "NumMedia": "0",
    }
    base.update(over)
    return base


def signed(payload: dict, token: str = TOKEN) -> dict:
    """Headers Twilio would send for this exact payload."""
    from twilio.request_validator import RequestValidator

    return {"X-Twilio-Signature": RequestValidator(token).compute_signature(URL, payload)}


@pytest.fixture(autouse=True)
def _env_independent(monkeypatch):
    """Pin the two settings that decide the signature outcome.

    `signed()` signs over the TestClient's own URL, so a real PUBLIC_BASE_URL in
    a developer's .env (a live tunnel, say) would make the app verify against a
    different URL and reject a correctly-signed request. Default both here;
    tests that exercise these set them explicitly.
    """
    monkeypatch.setattr(settings, "public_base_url", "")
    monkeypatch.setattr(channel_settings, "require_twilio_signature", False)

    # B's real ProcedureSearchImpl downloads a ~2GB embedding model on first
    # search. These tests exercise the channel, not retrieval, so pin the stub:
    # otherwise the suite stalls on a network fetch.
    from core import providers, stubs
    monkeypatch.setattr(providers, "procedures", stubs.StubProcedureSearch())


# ---- C2: webhook + signature ----------------------------------------------
def test_webhook_replies_with_twiml_in_dev_mode(monkeypatch):
    """No auth token configured (fresh .env) => dev mode, request goes through."""
    monkeypatch.setattr(settings, "twilio_auth_token", "")
    monkeypatch.setattr(channel_settings, "require_twilio_signature", False)
    r = client.post(whatsapp.WEBHOOK_PATH, data=form())
    assert r.status_code == 200
    assert "<Message>" in r.text and "</Response>" in r.text


def test_webhook_rejects_bad_signature(monkeypatch):
    monkeypatch.setattr(settings, "twilio_auth_token", TOKEN)
    r = client.post(whatsapp.WEBHOOK_PATH, data=form(),
                    headers={"X-Twilio-Signature": "obviously-wrong"})
    assert r.status_code == 403


def test_webhook_rejects_missing_signature(monkeypatch):
    monkeypatch.setattr(settings, "twilio_auth_token", TOKEN)
    assert client.post(whatsapp.WEBHOOK_PATH, data=form()).status_code == 403


def test_webhook_accepts_valid_signature(monkeypatch):
    monkeypatch.setattr(settings, "twilio_auth_token", TOKEN)
    payload = form()
    r = client.post(whatsapp.WEBHOOK_PATH, data=payload, headers=signed(payload))
    assert r.status_code == 200
    assert "<Message>" in r.text


def test_unverifiable_request_fails_closed_when_required(monkeypatch):
    """REQUIRE_TWILIO_SIGNATURE=true + no token => refuse, never answer blind."""
    monkeypatch.setattr(settings, "twilio_auth_token", "")
    monkeypatch.setattr(channel_settings, "require_twilio_signature", True)
    assert client.post(whatsapp.WEBHOOK_PATH, data=form()).status_code == 403


def test_public_base_url_wins_for_signature_check(monkeypatch):
    """Behind ngrok the signed URL is the public one, not the internal host."""
    monkeypatch.setattr(settings, "twilio_auth_token", TOKEN)
    monkeypatch.setattr(settings, "public_base_url", "https://daleel.example.org/")
    payload = form()
    from twilio.request_validator import RequestValidator

    sig = RequestValidator(TOKEN).compute_signature(
        "https://daleel.example.org" + whatsapp.WEBHOOK_PATH, payload
    )
    r = client.post(whatsapp.WEBHOOK_PATH, data=payload,
                    headers={"X-Twilio-Signature": sig})
    assert r.status_code == 200


# ---- privacy: the phone number never survives the edge --------------------
def test_user_ref_is_a_salted_hash():
    ref = identity.user_ref(PHONE, prefix="wa")
    assert ref.startswith("wa_")
    assert "70123456" not in ref and "+961" not in ref
    assert ref == identity.user_ref(PHONE, prefix="wa")          # stable


def test_user_ref_changes_with_the_salt(monkeypatch):
    before = identity.user_ref(PHONE)
    monkeypatch.setattr(settings, "session_hash_salt", "a-different-salt")
    assert identity.user_ref(PHONE) != before                     # rotation unlinks


def test_inquiry_carries_no_raw_phone():
    inq = whatsapp.build_inquiry(form())
    assert "70123456" not in inq.user_ref
    assert inq.channel == "whatsapp"
    assert inq.user_ref.startswith("wa_")


def test_phone_never_echoed_in_reply(monkeypatch):
    monkeypatch.setattr(settings, "twilio_auth_token", "")
    monkeypatch.setattr(channel_settings, "require_twilio_signature", False)
    r = client.post(whatsapp.WEBHOOK_PATH, data=form())
    assert "70123456" not in r.text


def test_weak_salt_is_flagged(monkeypatch):
    monkeypatch.setattr(settings, "session_hash_salt", "change-me")
    assert identity.salt_is_weak() is True
    body = client.get("/health/channels").json()
    assert body["privacy"]["salt_configured"] is False


# ---- C3: voice notes -------------------------------------------------------
def test_voice_note_is_transcribed(monkeypatch):
    monkeypatch.setattr(settings, "twilio_auth_token", "")
    monkeypatch.setattr(channel_settings, "require_twilio_signature", False)
    monkeypatch.setattr(whatsapp, "fetch_media", lambda url, form: b"fake-ogg-bytes")
    # B4's real Whisper transcriber rejects fake bytes; pin a fake so this tests the channel only
    from core import providers
    monkeypatch.setattr(providers, "transcriber", type("T", (), {
        "transcribe": lambda self, audio, mime: ("how do I get a health card", "en")})())

    payload = form(Body="", NumMedia="1",
                   MediaUrl0="https://api.twilio.com/media/ME1",
                   MediaContentType0="audio/ogg")
    r = client.post(whatsapp.WEBHOOK_PATH, data=payload)
    assert r.status_code == 200
    # the stub transcriber's placeholder text reached the pipeline
    assert "couldn't read" not in r.text
    assert "<Message>" in r.text


def test_voice_note_download_failure_is_graceful(monkeypatch):
    monkeypatch.setattr(settings, "twilio_auth_token", "")
    monkeypatch.setattr(channel_settings, "require_twilio_signature", False)

    def boom(url, form):
        raise RuntimeError("401 from Twilio")

    monkeypatch.setattr(whatsapp, "fetch_media", boom)
    payload = form(Body="", NumMedia="1",
                   MediaUrl0="https://api.twilio.com/media/ME1",
                   MediaContentType0="audio/ogg")
    r = client.post(whatsapp.WEBHOOK_PATH, data=payload)
    assert r.status_code == 200
    assert "couldn't read" in r.text          # core's fallback, not a crash


def test_media_download_is_size_capped(monkeypatch):
    """A huge media URL must raise rather than be read into memory."""
    monkeypatch.setattr(whatsapp, "MAX_AUDIO_BYTES", 10)

    class FakeResp:
        def raise_for_status(self): pass
        def iter_bytes(self): yield b"x" * 50
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(whatsapp.httpx, "stream", lambda *a, **k: FakeResp())
    with pytest.raises(ValueError):
        whatsapp.fetch_media("https://example.com/a.ogg", form())


def test_non_audio_media_is_not_transcribed(monkeypatch):
    called = []
    monkeypatch.setattr(whatsapp, "fetch_media",
                        lambda url, form: called.append(url) or b"")
    inq = whatsapp.build_inquiry(
        form(Body="", NumMedia="1", MediaUrl0="https://x/img", MediaContentType0="image/jpeg")
    )
    assert called == [] and inq.text == ""


# ---- reply rendering -------------------------------------------------------
def test_sources_are_appended_to_the_reply():
    a = Answer(text="Bring your ID.", tool="procedure", grounded=True,
               sources=[Source(title="MoPH", url="https://moph.gov.lb/x", checked_on="2026-10-10")])
    parts = render.for_whatsapp(a)
    assert "https://moph.gov.lb/x" in "".join(parts)
    assert "checked 2026-10-10" in "".join(parts)


def test_duplicate_sources_are_collapsed():
    src = Source(title="MoPH", url="https://moph.gov.lb/x")
    a = Answer(text="t", sources=[src, src])
    assert len(render.sources_lines(a)) == 1


def test_long_reply_is_split_under_the_whatsapp_limit():
    parts = render.chunk("word " * 2000)
    assert len(parts) > 1
    assert all(len(p) <= render.WHATSAPP_LIMIT for p in parts)


def test_empty_answer_still_sends_something():
    assert render.for_whatsapp(Answer(text="")) == ["…"]


# ---- C4: dashboard API -----------------------------------------------------
def test_metrics_falls_back_to_mock(monkeypatch):
    # Force the DB read to fail. Since D5 the metadata table can hold real
    # rows locally, so "no database" has to be simulated rather than assumed —
    # otherwise this passes or fails depending on whether Docker is up.
    def no_db():
        raise RuntimeError("no database")

    monkeypatch.setattr(metrics, "_fetch_rows", no_db)
    m = client.get("/api/metrics").json()
    assert m["source"] == "mock"
    for key in ("total_turns", "topics", "languages", "outcome_counts", "days",
                "escalation_rate", "unanswered_rate", "unanswered_topics", "cazas"):
        assert key in m
    assert m["total_turns"] > 0


def test_metrics_uses_real_rows_when_available(monkeypatch):
    # counts sit above MIN_CELL on purpose: a 1-conversation cell is withheld
    # now (see test_small_groups_are_withheld_from_breakdowns), so naming one
    # here would be asserting the privacy hole rather than the data path.
    rows = [
        {"topic": "vaccination", "caza": "Beirut", "lang": "ar", "outcome": "answered", "day": "2026-10-10", "n": 15},
        {"topic": "drug_price", "caza": "Aley", "lang": "fr", "outcome": "unanswered", "day": "2026-10-10", "n": 5},
    ]
    monkeypatch.setattr(metrics, "_fetch_rows", lambda: rows)
    m = client.get("/api/metrics").json()
    assert m["source"] == "metadata"
    assert m["total_turns"] == 20
    assert m["unanswered"] == 5 and m["unanswered_rate"] == 25.0
    assert m["unanswered_topics"][0]["label"] == "drug_price"


def test_metrics_counts_emergency_as_escalation():
    rows = [
        {"topic": "emergency", "lang": "ar", "outcome": "emergency", "day": "2026-10-10", "n": 1},
        {"topic": "x", "lang": "ar", "outcome": "answered", "day": "2026-10-10", "n": 3},
    ]
    m = metrics.summarise(rows, "metadata")
    assert m["escalations"] == 1 and m["escalation_rate"] == 25.0


def test_metrics_exposes_no_free_text():
    """Guard the privacy contract: only the six metadata columns may appear."""
    allowed = {"topic", "subtopic", "caza", "lang", "outcome", "day", "n"}
    assert set(metrics.MOCK_ROWS[0]) <= allowed


# ---- C0/C1/C5: pages + widget endpoints -----------------------------------
@pytest.mark.parametrize("path", ["/", "/dashboard", "/join"])
def test_pages_are_served(path):
    r = client.get(path)
    assert r.status_code == 200 and "<!doctype html>" in r.text.lower()


def test_widget_is_rtl_aware_and_calls_chat():
    html = client.get("/").text
    assert 'dir="rtl"' in html          # Arabic-first page
    assert 'dir="auto"' in html          # per-message direction
    assert "unicode-bidi:plaintext" in html.replace(" ", "")
    assert "/chat" in html


def test_session_endpoint_mints_a_pseudonymous_ref():
    ref = client.get("/api/session").json()["user_ref"]
    assert ref.startswith("web_") and len(ref) > 10
    assert client.get("/api/session").json()["user_ref"] != ref   # fresh each time


def test_hotlines_endpoint_lists_the_four_numbers():
    numbers = {h["number"] for h in client.get("/api/hotlines").json()["hotlines"]}
    assert {"1787", "1214", "1564", "140"} <= numbers


def test_channel_health_reports_wiring():
    body = client.get("/health/channels").json()
    assert body["ok"] is True
    assert "whatsapp" in body and "providers" in body


def test_whatsapp_info_and_qr():
    info = client.get("/api/whatsapp-info").json()
    assert "deep_link" in info and "configured" in info
    r = client.get("/qr.svg")
    assert r.status_code in {200, 501, 503}
    if r.status_code == 200:
        assert r.headers["content-type"].startswith("image/svg")


def test_register_is_idempotent():
    assert register(app) == []          # already mounted by channels.asgi


def test_unknown_transcriber_language_does_not_break_the_webhook(monkeypatch):
    """B's transcriber reporting 'arabic' or 'ar-LB' must not 500 the webhook."""
    monkeypatch.setattr(whatsapp, "transcribe_voice_note",
                        lambda url, mime, form: ("شو لازم جيب؟", "ar-LB"))
    inq = whatsapp.build_inquiry(
        form(Body="", NumMedia="1", MediaUrl0="https://x/a.ogg", MediaContentType0="audio/ogg")
    )
    assert inq.lang is None and inq.text


# ---- open item C1: k-anonymity on the dashboard ---------------------------
def test_small_groups_are_withheld_from_breakdowns():
    """topic + caza + day can identify one person in a small caza."""
    rows = [{"topic": "mental_health", "caza": "Bcharre", "lang": "ar",
             "outcome": "escalated", "day": "2026-10-10", "n": 1},
            {"topic": "vaccination", "caza": "Beirut", "lang": "ar",
             "outcome": "answered", "day": "2026-10-10", "n": 40}]
    out = metrics.summarise(rows, "metadata")
    labels = [c["label"] for c in out["cazas"]]
    assert "Bcharre" not in labels              # the identifying cell is gone
    withheld = [c for c in out["cazas"] if c.get("suppressed")]
    # secondary suppression: the page shows the total, so a lone 1 would be derivable
    # as total - published. Beirut is folded in too; the merged cell is never < MIN_CELL.
    assert withheld and withheld[0]["count"] >= metrics.MIN_CELL
    assert "Beirut" not in labels and withheld[0]["groups"] == 2


def test_secondary_suppression_keeps_large_groups_when_the_merge_is_big_enough():
    rows = [{"topic": "x", "caza": c, "lang": "ar", "outcome": "answered", "day": "2026-10-10", "n": n}
            for c, n in (("Beirut", 40), ("Aley", 30), ("Bcharre", 1))]
    cazas = metrics.summarise(rows, "metadata")["cazas"]
    published = {c["label"]: c["count"] for c in cazas if not c.get("suppressed")}
    other = [c for c in cazas if c.get("suppressed")][0]
    assert published == {"Beirut": 40} and other["count"] == 31   # Aley folded in, 1 not derivable


def test_two_small_groups_that_reach_the_minimum_are_merged_without_folding():
    rows = [{"topic": "x", "caza": c, "lang": "ar", "outcome": "answered", "day": "2026-10-10", "n": n}
            for c, n in (("Beirut", 40), ("A", 2), ("B", 3))]
    cazas = metrics.summarise(rows, "metadata")["cazas"]
    assert [c["label"] for c in cazas if not c.get("suppressed")] == ["Beirut"]
    assert [c["count"] for c in cazas if c.get("suppressed")] == [5]


def test_headline_totals_stay_exact_despite_suppression():
    """Suppression must not under-report escalations — that would be worse
    than useless to a ministry."""
    rows = [{"topic": "emergency", "caza": "Akkar", "lang": "ar",
             "outcome": "emergency", "day": "2026-10-10", "n": 2},
            {"topic": "x", "caza": "Beirut", "lang": "ar",
             "outcome": "answered", "day": "2026-10-10", "n": 30}]
    out = metrics.summarise(rows, "metadata")
    assert out["total_turns"] == 32
    assert out["escalations"] == 2              # counted, though the caza is withheld below
    assert out["outcome_counts"]["emergency"] == 2


def test_threshold_is_published_so_the_page_can_explain_itself():
    assert metrics.summarise(metrics.MOCK_ROWS, "mock")["min_cell"] == metrics.MIN_CELL


def test_the_withheld_notice_survives_the_top_n_cap():
    """The `withheld` entry sorts last, so a plain slice used to drop it just
    when there was enough data to need one: 26 cazas exist and a rehearsal
    seeds 12 labels. Suppression must never be silent on a ministry screen.
    """
    rows = [{"topic": "procedures", "caza": f"caza{i}", "lang": "ar",
             "outcome": "answered", "day": "2026-10-10", "n": 50 - i}
            for i in range(12)]
    rows.append({"topic": "procedures", "caza": "Bcharre", "lang": "ar",
                 "outcome": "answered", "day": "2026-10-10", "n": 1})

    cazas = metrics.summarise(rows, "metadata")["cazas"]
    published = [c for c in cazas if not c.get("suppressed")]
    withheld = [c for c in cazas if c.get("suppressed")]

    assert len(published) == 10                      # the cap still applies
    assert withheld and withheld[0]["count"] >= metrics.MIN_CELL   # and the notice came too


def test_the_cap_counts_published_labels_only():
    """A withheld entry must not consume one of the top-N slots."""
    rows = [{"topic": "procedures", "caza": f"caza{i}", "lang": "ar",
             "outcome": "answered", "day": "2026-10-10", "n": 9}
            for i in range(10)]
    rows += [{"topic": "procedures", "caza": name, "lang": "ar",
              "outcome": "answered", "day": "2026-10-10", "n": n}
             for name, n in (("Tiny", 2), ("Tiny2", 3))]       # together they reach MIN_CELL

    cazas = metrics.summarise(rows, "metadata")["cazas"]
    assert len([c for c in cazas if not c.get("suppressed")]) == 10
    assert len(cazas) == 11


# ---- open item C2: OpenStreetMap attribution (ODbL) -----------------------
def test_directory_answers_carry_the_osm_credit():
    ans = Answer(text="Pharmacy X, Main St", sources=[], tool="directory",
                 grounded=True, outcome="answered", lang="en")
    assert render.OSM_CREDIT in "\n".join(render.for_whatsapp(ans))


def test_non_directory_answers_do_not():
    ans = Answer(text="Bring your ID.", sources=[], tool="procedure",
                 grounded=True, outcome="answered", lang="en")
    assert render.OSM_CREDIT not in "\n".join(render.for_whatsapp(ans))


def test_credit_is_not_duplicated_if_core_already_added_it():
    ans = Answer(text=f"Pharmacy X. {render.OSM_CREDIT}", sources=[],
                 tool="directory", grounded=True, outcome="answered", lang="en")
    assert "\n".join(render.for_whatsapp(ans)).count(render.OSM_CREDIT) == 1


# ---- open item C3: mock topics must be the real closed vocabulary ---------
def test_mock_topics_are_all_in_the_declared_vocabulary():
    assert {r["topic"] for r in metrics.MOCK_ROWS} <= set(metrics.MOCK_TOPICS)


def test_mock_vocabulary_matches_the_real_metadata_writer():
    """`data.transcripts.topic()` is what actually fills `metadata.topic`, and
    `data.demo._TOPICS` seeds the same six for a rehearsal. If either renames a
    tool or adds a topic, this fails loudly instead of the mock dashboard
    drifting into topics the live page can never show.

    `ai.classifier.TOPICS` is deliberately NOT the reference: it is a wider,
    third vocabulary and nothing calls the classifier at runtime (B6 / H2).
    Pinning the mock to it is what hid `drug_price` — a quarter of every seeded
    rehearsal — from the mock view.
    """
    from typing import get_args

    from shared.contracts import Outcome, ToolName

    transcripts = pytest.importorskip("data.transcripts")

    # Both are closed Literals, so this is the complete set of topics any turn
    # can ever produce — not a sample of likely ones.
    reachable = {
        transcripts.topic(Answer(text="x", sources=[], tool=tool, grounded=True,
                                 outcome=outcome, lang="en"))
        for tool in get_args(ToolName)
        for outcome in get_args(Outcome)
    }
    assert set(metrics.MOCK_TOPICS) == reachable


def test_mock_rows_drop_the_caza_exactly_where_real_turns_do():
    """`transcripts.record` stores no caza for an emergency or a refusal, so a
    mock row carrying one would put a caza on the map that the live page never
    attributes to those topics."""
    transcripts = pytest.importorskip("data.transcripts")
    for row in metrics.MOCK_ROWS:
        if row["outcome"] in transcripts._NO_DETAIL:
            assert row["caza"] is None, row


def test_mock_cazas_are_canonical_names():
    """`metadata.caza` is a foreign key to `cazas.name_en`; an alias spelling
    ("Metn", "Nabatieh", "Keserwan") can never appear in real data."""
    import csv
    import pathlib

    seed = pathlib.Path(__file__).resolve().parents[1] / "src/data/seeds/cazas.csv"
    if not seed.exists():                       # D owns the seed; skip if it moves
        pytest.skip("cazas.csv not present")
    canonical = {r["name_en"] for r in csv.DictReader(seed.open(encoding="utf-8"))}
    used = {r["caza"] for r in metrics.MOCK_ROWS if r["caza"] is not None}
    assert used <= canonical, used - canonical


def test_mock_topics_satisfy_the_schema_check():
    """metadata.topic is CHECK (topic ~ '^[a-z_]{1,40}$')."""
    import re
    for t in metrics.MOCK_TOPICS:
        assert re.fullmatch(r"[a-z_]{1,40}", t), t


# ---- open item C4: the sparse window between empty and publishable -------
def test_real_but_tiny_data_is_flagged_sparse(monkeypatch):
    """One real turn must not look like a broken dashboard."""
    monkeypatch.setattr(metrics, "_fetch_rows",
                        lambda: [{"topic": "directory", "caza": "Beirut", "lang": "ar",
                                  "outcome": "answered", "day": "2026-10-10", "n": 1}])
    m = client.get("/api/metrics").json()
    assert m["source"] == "metadata"      # still honest about provenance
    assert m["sparse"] is True
    assert m["total_turns"] == 1


def test_mock_is_never_flagged_sparse():
    assert metrics.summarise(metrics.MOCK_ROWS, "mock")["sparse"] is False


def test_sufficient_real_data_is_not_sparse(monkeypatch):
    monkeypatch.setattr(metrics, "_fetch_rows",
                        lambda: [{"topic": "directory", "caza": "Beirut", "lang": "ar",
                                  "outcome": "answered", "day": "2026-10-10", "n": 40}])
    assert client.get("/api/metrics").json()["sparse"] is False


# ---- dashboard statistics fixes -------------------------------------------
def _row(day, outcome="answered", n=10, topic="procedures", caza="Beirut", lang="ar"):
    return {"topic": topic, "caza": caza, "lang": lang, "outcome": outcome, "day": day, "n": n}


def test_days_fill_gaps_and_report_the_real_period():
    out = metrics.summarise([_row("2026-10-10"), _row("2026-10-13", n=3)], "metadata")
    assert [d["label"] for d in out["days"]] == ["2026-10-10", "2026-10-11", "2026-10-12", "2026-10-13"]
    assert [d["count"] for d in out["days"]] == [10, 0, 0, 3]      # a 3-question day is not "withheld"
    assert out["period"] == {"start": "2026-10-10", "end": "2026-10-13"}


def test_one_day_of_data_has_a_period_and_one_point():
    out = metrics.summarise([_row("2026-10-10")], "metadata")
    assert len(out["days"]) == 1 and out["period"]["start"] == out["period"]["end"]


def test_headline_numbers_and_outcome_table_share_one_source():
    rows = [_row("2026-10-10", "answered", 30), _row("2026-10-10", "unanswered", 6, topic="other"),
            _row("2026-10-10", "emergency", 2, topic="emergency", caza=None),
            _row("2026-10-10", "escalated", 1), _row("2026-10-10", "refused", 3, topic="dosing_request")]
    out = metrics.summarise(rows, "metadata")
    oc = out["outcome_counts"]
    assert oc == {"answered": 30, "unanswered": 6, "refused": 3, "escalated": 1, "emergency": 2}
    assert sum(oc.values()) == out["total_turns"] == 42
    assert (out["answered"], out["unanswered"], out["emergency"], out["escalated_to_person"]) == (30, 6, 2, 1)
    assert out["answered_rate"] == round(100 * 30 / 42, 1)


def test_targets_are_absent_unless_configured(monkeypatch):
    for name in ("DASHBOARD_TARGET_ANSWERED_MIN", "DASHBOARD_TARGET_NO_SOURCE_MAX"):
        monkeypatch.delenv(name, raising=False)
    assert metrics.summarise([_row("2026-10-10")], "metadata")["targets"] == {
        "answered_min": None, "no_source_max": None}
    monkeypatch.setenv("DASHBOARD_TARGET_NO_SOURCE_MAX", "20")
    monkeypatch.setenv("DASHBOARD_TARGET_ANSWERED_MIN", "bad")
    assert metrics.summarise([_row("2026-10-10")], "metadata")["targets"] == {
        "answered_min": None, "no_source_max": 20.0}


def test_demo_mode_serves_synthetic_rows_and_never_touches_the_database(monkeypatch):
    def boom():
        raise AssertionError("demo mode must not read the database")

    monkeypatch.setattr(metrics, "_fetch_rows", boom)
    m = client.get("/api/metrics?demo=1").json()
    assert m["source"] == "demo"
    assert m["total_turns"] == 300 and len(m["days"]) == 30
    assert {r["label"] for r in m["languages"] if not r.get("suppressed")} == {"ar", "arabizi", "fr", "en"}
    assert all(m["outcome_counts"][k] > 0 for k in ("answered", "unanswered", "refused", "escalated", "emergency"))
    assert m["min_cell"] == metrics.MIN_CELL                    # same suppression rule as real data


def test_demo_flag_from_environment(monkeypatch):
    monkeypatch.setenv("DASHBOARD_DEMO", "1")
    assert client.get("/api/metrics").json()["source"] == "demo"
    monkeypatch.delenv("DASHBOARD_DEMO")
    monkeypatch.setattr(metrics, "_fetch_rows", lambda: [_row("2026-10-10")])
    assert client.get("/api/metrics").json()["source"] == "metadata"   # real rows are never demo-tagged


def test_demo_rows_use_only_the_metadata_columns_and_closed_topics():
    from channels.demo_metrics import demo_rows
    rows = demo_rows()
    assert set(rows[0]) <= {"topic", "subtopic", "caza", "lang", "outcome", "day", "n"}
    assert {r["topic"] for r in rows} <= set(metrics.MOCK_TOPICS)


# ---- dashboard: "by kind" breakdowns ---------------------------------------
def _krow(topic, sub, outcome="unanswered", n=6):
    return {"topic": topic, "subtopic": sub, "caza": "Beirut", "lang": "ar", "outcome": outcome,
            "day": "2026-10-10", "n": n}


def test_kinds_are_listed_per_topic_and_only_for_topics_that_have_them():
    rows = [_krow("procedures", "hospital_admission", n=9), _krow("drug_price", "diabetes", n=7),
            _krow("other", "should_be_ignored", n=8), _krow("procedures", "sample", n=6)]
    out = metrics.summarise(rows, "metadata")
    labels = {c["label"]: c["count"] for c in out["unanswered_kinds"] if not c.get("suppressed")}
    assert labels == {"procedures|hospital_admission": 9, "drug_price|diabetes": 7,
                      "other|": 8, "procedures|": 6}     # 'sample' (rehearsal marker) is not a kind


def test_kind_breakdown_uses_the_same_small_group_suppression():
    rows = [_krow("procedures", "hospital_admission", n=40), _krow("procedures", "vaccination", n=1)]
    kinds = metrics.summarise(rows, "metadata")["unanswered_kinds"]
    assert [c["label"] for c in kinds if not c.get("suppressed")] == []      # the lone 1 forces the 40 into the merge too
    assert kinds[-1]["suppressed"] and kinds[-1]["count"] == 41 and kinds[-1]["groups"] == 2


def test_kinds_only_count_unanswered_questions_in_the_gaps_list():
    rows = [_krow("procedures", "hospital_admission", "answered", 20), _krow("procedures", "vaccination", "unanswered", 6)]
    out = metrics.summarise(rows, "metadata")
    assert [c["label"] for c in out["unanswered_kinds"]] == ["procedures|vaccination"]
    assert {c["label"] for c in out["topic_kinds"]} == {"procedures|hospital_admission", "procedures|vaccination"}


def test_demo_rows_carry_kinds_from_the_closed_vocabulary():
    from channels.demo_metrics import demo_rows
    from ai import classifier
    allowed = {k for table in classifier.DETAIL.values() for k, _ in table} | set(classifier._DETAIL_OTHER.values())
    kinds = {r["subtopic"] for r in demo_rows() if r.get("subtopic")}
    assert kinds and kinds <= allowed
    assert all(r.get("subtopic") is None for r in demo_rows() if r["topic"] in ("other", "emergency", "dosing_request"))
