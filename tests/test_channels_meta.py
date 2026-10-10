"""Dev C: Meta WhatsApp Cloud API webhook tests.

Run: PYTHONPATH=src pytest -q
"""
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from channels import whatsapp_meta
from channels.asgi import app
from channels.settings_extra import channel_settings

client = TestClient(app)

SECRET = "test-app-secret"
VERIFY = "test-verify-token"
PHONE = "96170123456"
PATH = whatsapp_meta.WEBHOOK_PATH


@pytest.fixture(autouse=True)
def _meta_env(monkeypatch):
    """Pin every setting the handler reads, so a developer's real .env can't
    change the outcome (the same trap that bit the Twilio tests)."""
    monkeypatch.setattr(channel_settings, "meta_app_secret", SECRET)
    monkeypatch.setattr(channel_settings, "meta_verify_token", VERIFY)
    monkeypatch.setattr(channel_settings, "meta_access_token", "test-token")
    monkeypatch.setattr(channel_settings, "meta_phone_number_id", "123456")
    monkeypatch.setattr(channel_settings, "require_meta_signature", False)
    # never let a test reach the network: neither the Graph API reply nor B's
    # ProcedureSearchImpl, which downloads a ~2GB embedding model on first use
    monkeypatch.setattr(whatsapp_meta, "send_text", lambda to, body: True)
    from core import providers, stubs
    monkeypatch.setattr(providers, "procedures", stubs.StubProcedureSearch())


def payload(text="how do I renew my medication card?", **over) -> dict:
    msg = {"from": PHONE, "id": "wamid.TEST", "timestamp": "1760000000",
           "type": "text", "text": {"body": text}}
    msg.update(over)
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": "15550001111", "phone_number_id": "123456"},
            "contacts": [{"profile": {"name": "Should Be Ignored"}, "wa_id": PHONE}],
            "messages": [msg],
        }}]}],
    }


def signed(body: bytes, secret: str = SECRET) -> dict:
    mac = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": f"sha256={mac}", "Content-Type": "application/json"}


def post(data: dict, secret: str = SECRET):
    raw = json.dumps(data).encode()
    return client.post(PATH, content=raw, headers=signed(raw, secret))


# ---- verification handshake ------------------------------------------------
def test_handshake_echoes_challenge_as_plain_text():
    r = client.get(PATH, params={"hub.mode": "subscribe",
                                 "hub.verify_token": VERIFY,
                                 "hub.challenge": "1158201444"})
    assert r.status_code == 200
    assert r.text == "1158201444"          # bare body, not JSON-wrapped
    assert r.headers["content-type"].startswith("text/plain")


def test_handshake_rejects_wrong_token():
    r = client.get(PATH, params={"hub.mode": "subscribe",
                                 "hub.verify_token": "wrong",
                                 "hub.challenge": "123"})
    assert r.status_code == 403


# ---- signature -------------------------------------------------------------
def test_accepts_valid_signature():
    assert post(payload()).status_code == 200


def test_rejects_bad_signature():
    assert post(payload(), secret="not-the-secret").status_code == 403


def test_rejects_missing_signature():
    raw = json.dumps(payload()).encode()
    r = client.post(PATH, content=raw, headers={"Content-Type": "application/json"})
    assert r.status_code == 403


def test_unverifiable_request_fails_closed_when_required(monkeypatch):
    monkeypatch.setattr(channel_settings, "meta_app_secret", "")
    monkeypatch.setattr(channel_settings, "require_meta_signature", True)
    raw = json.dumps(payload()).encode()
    r = client.post(PATH, content=raw, headers={"Content-Type": "application/json"})
    assert r.status_code == 403


# ---- payload handling ------------------------------------------------------
def test_answers_a_text_message():
    r = post(payload())
    assert r.status_code == 200 and r.json()["handled"] == 1


def test_delivery_receipt_is_ignored_with_200():
    """Status callbacks hit the same endpoint; a non-200 makes Meta retry."""
    statuses = {"object": "whatsapp_business_account", "entry": [{"id": "W", "changes": [
        {"field": "messages", "value": {"statuses": [{"id": "wamid.X", "status": "delivered"}]}}]}]}
    r = post(statuses)
    assert r.status_code == 200 and r.json()["status"] == "ignored"


def test_batched_messages_all_handled():
    data = payload()
    msgs = data["entry"][0]["changes"][0]["value"]["messages"]
    msgs.append({"from": PHONE, "id": "wamid.TEST2", "type": "text",
                 "text": {"body": "wen aqrab saydaliyye?"}})
    r = post(data)
    assert r.json()["handled"] == 2


def test_unparseable_body_is_rejected():
    raw = b"not json"
    assert client.post(PATH, content=raw, headers=signed(raw)).status_code == 400


def test_unsupported_type_still_answers():
    """An image shouldn't 500 — it becomes an empty inquiry the pipeline can
    answer with its fallback."""
    r = post(payload(type="image", text=None))
    assert r.status_code == 200


# ---- privacy ---------------------------------------------------------------
def test_user_ref_is_hashed_and_matches_the_twilio_namespace():
    from channels import whatsapp as twilio_ch

    msg = payload()["entry"][0]["changes"][0]["value"]["messages"][0]
    inq = whatsapp_meta.build_inquiry(msg)

    assert PHONE not in inq.user_ref
    assert inq.user_ref.startswith("wa_")
    # same human on either provider must hash to the same ref
    twilio_inq = twilio_ch.build_inquiry(
        {"From": f"whatsapp:+{PHONE}", "Body": "x", "MessageSid": "SM1", "NumMedia": "0"}
    )
    assert inq.user_ref == twilio_inq.user_ref


def test_profile_name_never_reaches_the_inquiry():
    msg = payload()["entry"][0]["changes"][0]["value"]["messages"][0]
    inq = whatsapp_meta.build_inquiry(msg)
    assert "Should Be Ignored" not in (inq.text or "")
    assert "Should Be Ignored" not in inq.user_ref
