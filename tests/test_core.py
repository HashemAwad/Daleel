"""Dev A core tests: routing, safety (multilingual), grounding gate, voice path."""
import pytest
from shared.contracts import Inquiry, ToolResult
from core import pipeline, router


def _inq(text="", audio_url=None, lang=None):
    return Inquiry(id="t", channel="web", text=text, user_ref="t", audio_url=audio_url, lang=lang)


# ---- A4: routing picks the right tool -------------------------------------
@pytest.mark.parametrize("text,expected", [
    ("how do I get my cancer medicine from the ministry?", "procedure"),
    ("nearest pharmacy in Aley", "directory"),
    ("أقرب مستشفى", "directory"),
    ("combien coûte le Concor 5?", "medicine"),
    ("سعر الدوا", "medicine"),
])
def test_router_picks_tool(text, expected):
    assert router.route(_inq(text)).tool == expected


# ---- A5: safety, multilingual ---------------------------------------------
@pytest.mark.parametrize("text", [
    "my father is not breathing",
    "بدي موت",
    "crise cardiaque",
])
def test_emergency(text):
    a = pipeline.handle(_inq(text))
    assert a.outcome == "emergency" and "140" in a.text


@pytest.mark.parametrize("text", [
    "what dose of panadol for my baby?",
    "كم حبة لازم آخذ",
    "quelle posologie",
])
def test_advice_refused(text):
    assert pipeline.handle(_inq(text)).outcome == "refused"


# ---- A3: grounding gate falls back when no tool result --------------------
def test_grounding_fallback(monkeypatch):
    monkeypatch.setattr(router, "route", lambda inq: ToolResult(tool="procedure"))
    a = pipeline.handle(_inq("something with no source"))
    assert a.grounded is False and a.outcome == "unanswered" and "1787" in a.text


# ---- A6: voice note is transcribed before routing -------------------------
def test_voice_note_transcribed(monkeypatch):
    monkeypatch.setattr(pipeline, "_fetch_audio", lambda url: b"fake-audio")
    a = pipeline.handle(_inq(text="", audio_url="https://example.com/vn.ogg"))
    # stub transcriber yields placeholder text -> pipeline still produces an answer
    assert a.text and a.outcome in {"answered", "unanswered"}


def test_unreadable_voice_note(monkeypatch):
    def boom(url):
        raise RuntimeError("fetch failed")
    monkeypatch.setattr(pipeline, "_fetch_audio", boom)
    a = pipeline.handle(_inq(text="", audio_url="https://example.com/vn.ogg"))
    assert a.outcome == "unanswered" and "couldn't read" in a.text
