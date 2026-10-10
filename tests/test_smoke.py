"""Smoke tests — must stay green. Run: PYTHONPATH=src pytest -q
These are the shared 'is it still wired?' checks every PR must pass."""
from fastapi.testclient import TestClient
from core.app import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["ok"] is True


def test_chat_returns_answer():
    r = client.post("/chat", json={"channel": "web", "text": "how do I get my medicine?", "user_ref": "t"})
    assert r.status_code == 200
    body = r.json()
    assert "text" in body and body["text"]
    assert body["tool"] in {"procedure", "directory", "medicine", "hotline", "none"}


def test_emergency_shortcircuits():
    r = client.post("/chat", json={"channel": "web", "text": "my father is not breathing", "user_ref": "t"})
    assert r.json()["outcome"] == "emergency"
    assert "140" in r.json()["text"]


def test_medical_advice_refused():
    r = client.post("/chat", json={"channel": "web", "text": "what dose of panadol for my baby?", "user_ref": "t"})
    assert r.json()["outcome"] == "refused"
