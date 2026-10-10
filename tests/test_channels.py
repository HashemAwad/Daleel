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
def test_metrics_falls_back_to_mock():
    m = client.get("/api/metrics").json()
    assert m["source"] == "mock"
    for key in ("total_turns", "topics", "languages", "outcomes", "days",
                "escalation_rate", "unanswered_rate", "unanswered_topics", "cazas"):
        assert key in m
    assert m["total_turns"] > 0


def test_metrics_uses_real_rows_when_available(monkeypatch):
    rows = [
        {"topic": "vaccination", "caza": "Beirut", "lang": "ar", "outcome": "answered", "day": "2026-10-10", "n": 3},
        {"topic": "drug_price", "caza": "Aley", "lang": "fr", "outcome": "unanswered", "day": "2026-10-10", "n": 1},
    ]
    monkeypatch.setattr(metrics, "_fetch_rows", lambda: rows)
    m = client.get("/api/metrics").json()
    assert m["source"] == "metadata"
    assert m["total_turns"] == 4
    assert m["unanswered"] == 1 and m["unanswered_rate"] == 25.0
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
